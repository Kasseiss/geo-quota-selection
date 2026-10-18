"""Filename-selected, credited examples from the predetermined spatial checkpoint.

This descriptive illustration does not change the locked experiment or select
examples by performance. Only the two explicitly credited catalogues are used.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.text import Text
import numpy as np
import torch

from core import confusion
from v2_run import ROOT, load_locked
from v2_segmentation import (ResNet18UNet, load_pair, normalized_image,
                             seed_all, sha, state_sha)

NAMES=['Void','Bareland','Rangeland','Developed space','Road','Tree','Water','Agriculture land','Building']
HEX=['#f0f0f0','#ddcc77','#88ccee','#cc6677','#999999','#117733','#332288','#999933','#882255']
PALETTE=np.array([[int(h[i:i+2],16) for i in (1,3,5)] for h in HEX],dtype=np.uint8)
REGIONS=['al_qurnah','baybay']
PRINT_WIDTH_INCHES=4.95
CREDITS={
    'al_qurnah':{'provider':'Bilal Koç','source':'OpenAerialMap / Open Imagery Network contributors',
                 'url':'https://map.openaerialmap.org/','license':'CC BY4.0'},
    'baybay':{'provider':'SkyEye','source':'OpenAerialMap / Open Imagery Network contributors',
              'url':'https://map.openaerialmap.org/','license':'CC BY4.0'}}


def main():
    freeze,design,manifest,index,development,panel=load_locked()
    reload=json.loads((ROOT/'evidence/v2/checkpoint_reload.json').read_text())
    assert reload['passed'] and reload['matched_images']==72
    destination=ROOT/'evidence/v2/illustration_selection.json'
    selected=[sorted([r for r in panel if r['region']==region],key=lambda r:r['id'])[0] for region in REGIONS]
    selection={'created_utc':datetime.now(timezone.utc).isoformat(),
        'rule':'First two alphabetical new-panel regions whose official catalogue has a single unambiguous CC BY4.0 source, then first alphabetical image ID in each. Catalogue-level attribution; exact upstream scene URI not independently resolved.',
        'regions':REGIONS,'ids':[r['id'] for r in selected],
        'scope':'Descriptive illustration fixed after the experiment freeze and first fits, before inspecting these images or per-image outcomes; not a prospective statistical comparison.',
        'source_attribution_document_sha256':sha(ROOT/'docs/v2_data_attribution.md'),
        'performance_or_appearance_used_to_select_examples':False,'catalogue_credits':CREDITS}
    if destination.exists():
        existing=json.loads(destination.read_text())
        assert existing['ids']==selection['ids'] and existing['rule']==selection['rule']
        selection=existing
    else:destination.write_text(json.dumps(selection,indent=2)+'\n',encoding='utf-8')
    result_path=ROOT/'evidence/v2/runs/resnet18_unet/source0_skewed5_1_b12_s0_i0_region_kcenter/result.json'
    result=json.loads(result_path.read_text());checkpoint=result['checkpoint']
    assert sha(ROOT/checkpoint['path'])==checkpoint['sha256']==reload['checkpoint_sha256']
    torch.set_num_threads(8);seed_all(0)
    model=ResNet18UNet(pretrained=False)
    model.load_state_dict(torch.load(ROOT/checkpoint['path'],map_location='cpu',weights_only=True),strict=True)
    model.eval();assert state_sha(model)==checkpoint['state_sha256']
    reference={r['id']:r for r in result['test']['images']}
    plt.rcParams.update({'font.family':'Arial','font.size':9,'svg.fonttype':'none','pdf.fonttype':42})
    fig,axes=plt.subplots(2,3,figsize=(PRINT_WIDTH_INCHES,4.6))
    checks=[]
    for row,record in enumerate(selected):
        rgb,truth=load_pair(record,ROOT/'v2/data')
        with torch.inference_mode():
            logits=model(normalized_image(rgb,'cpu'));assert torch.isfinite(logits).all()
            prediction=logits.argmax(1)[0].numpy()
        cm=confusion(truth.numpy(),prediction,ignore=255)
        assert cm.tolist()==reference[record['id']]['confusion']
        displayed_truth=np.where(truth.numpy()==255,0,truth.numpy()+1).astype(np.uint8)
        displayed_prediction=np.where(truth.numpy()==255,0,prediction+1).astype(np.uint8)
        panels=[rgb.permute(1,2,0).numpy(),PALETTE[displayed_truth],PALETTE[displayed_prediction]]
        for col,array in enumerate(panels):
            axis=axes[row,col];axis.imshow(array,interpolation='nearest');axis.set_xticks([]);axis.set_yticks([])
            for spine in axis.spines.values():spine.set_visible(False)
            name=['RGB','Reference mask','Predicted mask'][col]
            axis.set_title(chr(ord('a')+row*3+col)+'   '+name,loc='left',fontsize=9,fontweight='bold',pad=5)
        axes[row,0].set_ylabel({'al_qurnah':'Al Qurnah','baybay':'Baybay'}[record['region']],fontsize=9)
        checks.append({'id':record['id'],'confusion_exact_match':True,
                       'prediction_array_sha256':hashlib.sha256(prediction.tobytes()).hexdigest()})
    fig.legend([Patch(facecolor=h) for h in HEX],NAMES,loc='lower center',
               ncol=3,frameon=False,fontsize=9,bbox_to_anchor=(.52,.005))
    fig.subplots_adjust(left=.075,right=.99,top=.95,bottom=.16,hspace=.23,wspace=.035)
    fig.canvas.draw()
    minimum_font_pt=min(t.get_fontsize() for t in fig.findobj(Text) if t.get_text())
    panel_widths=[a.get_window_extent().width/fig.dpi for a in axes.flat]
    minimum_native_dpi=min(448/w for w in panel_widths)
    assert minimum_font_pt>=9 and minimum_native_dpi>=300
    outputs={};out=ROOT/'figures/v2';out.mkdir(exist_ok=True)
    for extension in ['svg','pdf','png']:
        path=out/('qualitative_fixed_examples.'+extension)
        fig.savefig(path,dpi=320,metadata={'Creator':'Predetermined trained checkpoint; credited public catalogue examples'})
        outputs[path.relative_to(ROOT).as_posix()]=sha(path)
    plt.close(fig)
    caption=('Filename-selected examples from Al Qurnah and Baybay. RGB images and reference masks were processed to448×448; predicted masks use the predetermined source0, paired fit seed0, quota k-center checkpoint. These two illustrations concern one fit; numerical comparisons use all planned fits. Void is light grey in masks, and predictions in void locations are hidden as in scoring. Source catalogue credits: Bilal Koç (Al Qurnah) and SkyEye (Baybay), OpenAerialMap / Open Imagery Network contributors, CC BY4.0 (https://creativecommons.org/licenses/by/4.0/), via OpenEarthMap. RGB images were bilinearly resized and labels nearest-resized; the categorical palette is assigned for display. Exact upstream scene URIs were not independently resolved.')
    report={'passed':True,'created_utc':datetime.now(timezone.utc).isoformat(),
        'selection_sha256':sha(destination),'checkpoint_sha256':checkpoint['sha256'],
        'result_sha256':sha(result_path),'code_sha256':sha(Path(__file__)),
        'checks':checks,'output_sha256':outputs,'caption':caption,'refitting_performed':False,
        'recommended_print_width_inches':PRINT_WIDTH_INCHES,'height_inches':4.6,
        'minimum_font_pt_at_recommended_width':minimum_font_pt,
        'minimum_native_raster_dpi_at_recommended_width':minimum_native_dpi,
        'visual_review':'PENDING after print-size revision',
        'comparative_performance_claim':False,'public_posting_performed':False}
    (ROOT/'evidence/v2/qualitative_verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
