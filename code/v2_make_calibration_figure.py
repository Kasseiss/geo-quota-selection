"""Plot completed source-only calibration; no new-panel outcomes are read."""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.text import Text
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source=ROOT/'evidence/v2/calibration/calibration.json'
    calibration=json.loads(source.read_text());assert calibration['complete'] and len(calibration['splits'])==3
    plt.rcParams.update({'font.family':'Arial','font.size':9,'svg.fonttype':'none',
        'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,
        'axes.linewidth':.7,'xtick.major.width':.7,'ytick.major.width':.7})
    fig,axes=plt.subplots(1,3,figsize=(6.5,2.85),sharey=True)
    inputs={'evidence/v2/calibration/calibration.json':sha(source)}
    for axis,part,label in zip(axes,calibration['splits'],'abc'):
        settings=part['settings']
        for lr,color,marker in [(0.0001,'#0072B2','o'),(0.0003,'#D55E00','s')]:
            rows=sorted([r for r in settings if r['encoder_lr']==lr],key=lambda r:r['steps'])
            assert [r['steps'] for r in rows]==[300,600,1200]
            axis.plot([r['steps'] for r in rows],[100*r['validation_union_miou'] for r in rows],
                color=color,marker=marker,markersize=4,lw=1.2,label=f'Encoder LR {lr:g}')
            for r in rows:inputs[r['record']]=sha(ROOT/r['record'])
        best=part['chosen'];axis.plot(best['steps'],100*best['validation_union_miou'],
            marker='*',color='black',markersize=10,zorder=4,label='Chosen recipe')
        axis.set_title(f'{label}   {part["source_split"]}',loc='left',fontsize=10,fontweight='bold')
        axis.set_xlabel('Training steps');axis.set_xticks([300,600,1200]);axis.set_xlim(200,1300)
        axis.set_ylim(10,33);axis.set_yticks([10,15,20,25,30]);axis.grid(axis='y',color='#e5e5e5',lw=.5)
    axes[0].set_ylabel('Regional validation mIoU (%)')
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=3,frameon=False,bbox_to_anchor=(.5,.005))
    fig.subplots_adjust(left=.09,right=.99,bottom=.30,top=.87,wspace=.22)
    fig.canvas.draw()
    minimum_font_pt=min(t.get_fontsize() for t in fig.findobj(Text) if t.get_text())
    assert minimum_font_pt>=9
    out=ROOT/'figures/v2';out.mkdir(exist_ok=True)
    outputs={}
    for extension in ('svg','pdf','png'):
        path=out/('source_calibration.'+extension)
        fig.savefig(path,dpi=320,metadata={'Creator':'Measured source-only calibration'})
        outputs[path.relative_to(ROOT).as_posix()]=sha(path)
    plt.close(fig)
    report={'input_sha256':inputs,'output_sha256':outputs,'new_panel_outcomes_read':False,
        'recommended_print_width_inches':6.5,'height_inches':2.85,
        'minimum_font_pt_at_recommended_width':minimum_font_pt,
        'visual_review':'PENDING after print-size revision',
        'caption':'Source-only calibration of the complete spatial model. Curves show equal-region union-class mIoU on each allocation\'s four old validation regions. Stars indicate the predefined maximum-score recipe, with fewer steps then lower learning rate breaking ties. Absolute scores across panels refer to different validation sets and are not matched model comparisons. The decoder learning rate is ten times the encoder rate. No new-panel outcome informed these choices.'}
    (ROOT/'evidence/v2/calibration_figure.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
