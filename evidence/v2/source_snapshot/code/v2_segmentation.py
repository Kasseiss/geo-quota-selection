"""Trainable ResNet18 U-Net-style segmentation model for the extension study.

This is an existing encoder/skip-decoder design, not a novel architecture.
Only development data may determine the fixed optimization recipe.
"""
from __future__ import annotations

import hashlib
import json
import random
import time
import platform
from pathlib import Path

import numpy as np
from PIL import Image
import torch
from torch import nn
from torch.nn import functional as F
from torchvision.models import resnet18, ResNet18_Weights

ROOT = Path(__file__).resolve().parents[1]
MEAN = torch.tensor([.485, .456, .406])[None, :, None, None]
STD = torch.tensor([.229, .224, .225])[None, :, None, None]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()


def state_sha(model):
    h=hashlib.sha256()
    for name,value in model.state_dict().items():
        a=value.detach().cpu().contiguous().numpy()
        h.update(name.encode());h.update(str(a.dtype).encode());h.update(str(a.shape).encode());h.update(a.tobytes())
    return h.hexdigest()


def records_sha(records):
    return hashlib.sha256(json.dumps(sorted(records,key=lambda r:r['id']),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def runtime_identity(device):
    return dict(torch=torch.__version__,numpy=np.__version__,python=platform.python_version(),
                threads=torch.get_num_threads(),device=str(device),
                device_name=torch.cuda.get_device_name() if str(device).startswith('cuda') else platform.processor(),
                pretrained_weight_sha256=sha(Path(torch.hub.get_dir())/'checkpoints/resnet18-f37072fd.pth'))


def seed_all(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)


class DecoderBlock(nn.Module):
    def __init__(self, incoming, skip, outgoing):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv2d(incoming + skip, outgoing, 3, padding=1, bias=False),
            nn.GroupNorm(min(8, outgoing), outgoing), nn.ReLU(inplace=True),
            nn.Conv2d(outgoing, outgoing, 3, padding=1, bias=False),
            nn.GroupNorm(min(8, outgoing), outgoing), nn.ReLU(inplace=True))

    def forward(self, x, skip):
        x = F.interpolate(x, size=skip.shape[-2:], mode='bilinear', align_corners=False)
        return self.layers(torch.cat([x, skip], dim=1))


class ResNet18UNet(nn.Module):
    def __init__(self, pretrained=True):
        super().__init__()
        backbone = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1 if pretrained else None)
        self.stem = nn.Sequential(backbone.conv1, backbone.bn1, backbone.relu)
        self.pool = backbone.maxpool
        self.enc1, self.enc2 = backbone.layer1, backbone.layer2
        self.enc3, self.enc4 = backbone.layer3, backbone.layer4
        self.dec3 = DecoderBlock(512, 256, 128)
        self.dec2 = DecoderBlock(128, 128, 64)
        self.dec1 = DecoderBlock(64, 64, 32)
        self.dec0 = DecoderBlock(32, 64, 16)
        self.output = nn.Conv2d(16, 8, 1)

    def train(self, mode=True):
        super().train(mode)
        # Small batches: use pretrained running statistics; affine parameters
        # and every encoder convolution remain trainable.
        for module in self.modules():
            if isinstance(module, nn.BatchNorm2d): module.eval()
        return self

    def forward(self, x):
        size = x.shape[-2:]
        a = self.stem(x); b = self.enc1(self.pool(a)); c = self.enc2(b)
        d = self.enc3(c); e = self.enc4(d)
        z = self.dec0(self.dec1(self.dec2(self.dec3(e, d), c), b), a)
        return F.interpolate(self.output(z), size=size, mode='bilinear', align_corners=False)


def load_pair(record, base):
    """Load preprocessed448 data using explicit RGB and label subrecords."""
    rgb_path = Path(base) / record['rgb']['relative_path']
    label_path = Path(base) / record['label']['relative_path']
    if sha(rgb_path) != record['rgb']['sha256'] or sha(label_path) != record['label']['sha256']:
        raise ValueError('Processed image checksum mismatch: ' + record['id'])
    rgb = np.asarray(Image.open(rgb_path).convert('RGB')).copy()
    mask = np.asarray(Image.open(label_path)).copy()
    if rgb.shape != (448, 448, 3) or mask.shape != (448, 448): raise ValueError('Expected448 pair')
    if not set(np.unique(mask)) <= set(range(9)): raise ValueError('Unexpected mask class')
    truth = mask.astype(np.int64) - 1
    truth[mask == 0] = 255
    return torch.from_numpy(rgb).permute(2, 0, 1), torch.from_numpy(truth)


def make_batch(images, rng, batch_size=2, crop=224):
    xs, ys = [], []
    for _ in range(batch_size):
        # Crop randomness is tied to the optimization seed, shared by policies.
        index = int(rng.integers(len(images)))
        x, y = images[index]
        for attempt in range(16):
            top, left = rng.integers(0, 449-crop, size=2)
            xx, yy = x[:, top:top+crop, left:left+crop], y[top:top+crop, left:left+crop]
            if torch.any(yy != 255): break
        if not torch.any(yy != 255): raise ValueError('Repeated all-void crops in a selected training image')
        if rng.random() < .5: xx, yy = xx.flip(-1), yy.flip(-1)
        if rng.random() < .5: xx, yy = xx.flip(-2), yy.flip(-2)
        rotations = int(rng.integers(4))
        xx, yy = xx.rot90(rotations, [-2, -1]), yy.rot90(rotations, [-2, -1])
        xs.append(xx); ys.append(yy)
    x = torch.stack(xs).float().div_(255)
    return (x - MEAN) / STD, torch.stack(ys)


def normalized_image(rgb, device):
    return ((rgb[None].float()/255 - MEAN) / STD).to(device)


@torch.inference_mode()
def evaluate(model, records, base, device):
    from core import confusion, aggregate
    was_training = model.training
    model.eval(); entries=[]
    for record in records:
        x, truth = load_pair(record, base)
        logits = model(normalized_image(x, device))
        if not torch.isfinite(logits).all():raise RuntimeError('Nonfinite evaluation logits')
        pred = logits.argmax(1)[0].cpu().numpy()
        cm = confusion(truth.numpy(), pred, ignore=255)
        entries.append(dict(id=record['id'], region=record['region'], confusion=cm.tolist()))
    model.train(was_training)
    result = aggregate(entries)
    result['equal_region_union_miou'] = float(np.mean([
        x['union_class_miou'] for x in result['regions'].values()]))
    return dict(images=entries, aggregate=result)


def fit(records, base, *, seed, encoder_lr, steps, device='cpu', batch_size=2,
        crop=224, validation=None, checkpoints=(), log_every=50, log_callback=None):
    if not records or len({r['id'] for r in records})!=len(records): raise ValueError('Empty/duplicate training IDs')
    if validation is not None and {r['id'] for r in records}&{r['id'] for r in validation}:
        raise ValueError('Training/validation image overlap')
    seed_all(seed)
    model = ResNet18UNet(pretrained=True).to(device).train()
    identity=dict(initial_model_state_sha256=state_sha(model),
        selected_ids=[r['id'] for r in records],
        selected_record_sha256=hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest(),
        pretrained_weight_sha256=sha(Path(torch.hub.get_dir())/'checkpoints/resnet18-f37072fd.pth'),
        model_code_sha256=sha(Path(__file__)),torch=torch.__version__,numpy=np.__version__,
        python=platform.python_version(),threads=torch.get_num_threads(),
        device_name=torch.cuda.get_device_name() if str(device).startswith('cuda') else platform.processor())
    encoder = [p for name,p in model.named_parameters() if name.startswith(('stem.','enc'))]
    decoder = [p for name,p in model.named_parameters() if not name.startswith(('stem.','enc'))]
    optimizer = torch.optim.AdamW([{'params':encoder,'lr':encoder_lr},
                                  {'params':decoder,'lr':10*encoder_lr}],weight_decay=1e-4)
    images = [load_pair(record, base) for record in records]
    rng = np.random.default_rng(seed)
    logs=[]; validations=[]; started=time.monotonic()
    for step in range(1,steps+1):
        x,y=make_batch(images,rng,batch_size,crop);x=x.to(device);y=y.to(device)
        # Constant rates make calibration checkpoints exact prefixes of fits
        # stopped at that step; no max-step-dependent schedule is used.
        optimizer.zero_grad(set_to_none=True)
        loss=F.cross_entropy(model(x),y,ignore_index=255)
        if not torch.isfinite(loss): raise RuntimeError('Nonfinite training loss')
        loss.backward();optimizer.step()
        if step==1 or step%log_every==0 or step==steps:
            entry=dict(step=step,loss=float(loss.detach()),elapsed_seconds=time.monotonic()-started)
            logs.append(entry)
            if log_callback is not None:log_callback(entry)
        if validation is not None and step in checkpoints:
            if not all(torch.isfinite(v).all() for v in model.state_dict().values()):raise RuntimeError('Nonfinite model state')
            score=evaluate(model,validation,base,device)
            validations.append(dict(step=step,validation=score,model_state_sha256=state_sha(model)))
    if not all(torch.isfinite(v).all() for v in model.state_dict().values()):raise RuntimeError('Nonfinite final model state')
    return model,dict(identity=identity,final_model_state_sha256=state_sha(model),all_final_parameters_finite=True,log=logs,validation=validations,elapsed_seconds=time.monotonic()-started,
                      encoder_lr=encoder_lr,decoder_lr=10*encoder_lr,steps=steps,seed=seed,
                      batch_size=batch_size,crop=crop,device=str(device),
                      trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad))


def software_check():
    """Real tensor optimization check; no held-out scientific evidence."""
    torch.set_num_threads(8);seed_all(7)
    m=ResNet18UNet(pretrained=True).train()
    x=torch.randn(2,3,96,96);y=torch.randint(8,(2,96,96))
    before=m.stem[0].weight.detach().clone();bn=m.stem[1].running_mean.detach().clone()
    o=torch.optim.AdamW(m.parameters(),lr=1e-4)
    started=time.monotonic();losses=[]
    for _ in range(3):
        o.zero_grad(set_to_none=True);logits=m(x);assert logits.shape==(2,8,96,96)
        loss=F.cross_entropy(logits,y);loss.backward()
        assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in m.parameters())
        o.step();losses.append(float(loss.detach()))
    assert not torch.equal(before,m.stem[0].weight)
    assert torch.equal(bn,m.stem[1].running_mean)
    m.eval()
    with torch.no_grad():assert m(torch.randn(1,3,111,123)).shape==(1,8,111,123)
    return dict(passed=True,all_encoder_and_decoder_parameters_have_finite_gradients=True,
                first_encoder_convolution_changed=True,batchnorm_running_stats_fixed=True,
                losses=losses,seconds=time.monotonic()-started,torch=torch.__version__,
                parameters=sum(p.numel() for p in m.parameters()),device='cpu',
                pretrained_weight_sha256=sha(Path(torch.hub.get_dir())/'checkpoints/resnet18-f37072fd.pth'))


if __name__=='__main__':
    r=software_check();out=ROOT/'evidence/v2/software';out.mkdir(parents=True,exist_ok=True)
    (out/'segmentation_validation.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
    print(json.dumps(r,indent=2))
