"""Deterministic experiments; every reported metric is computed, not hard-coded."""
from __future__ import annotations
import csv
from dataclasses import asdict, replace
import importlib.metadata
import json
import platform
from pathlib import Path
from time import perf_counter
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .analysis import AnalysisConfig, analyze, axial_error
from .synthetic import stripes, quantized, generate_samples
from .io import load_image
from .export import write_export

ANGLES=list(range(0,180,15))
NOISE_LEVELS=[0.,.05,.15,.30]
SEEDS=list(range(5))


def save_csv(path,rows):
    if not rows:return
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def save_plot(fig,path):
    fig.tight_layout();fig.savefig(path,dpi=180,bbox_inches='tight');plt.close(fig)


def summarize(rows,group_key):
    output=[]
    for group in sorted(set(r[group_key] for r in rows)):
        block=[r for r in rows if r[group_key]==group]
        out={group_key:group,'n_images':len(block)}
        for method in ['spatial','fourier']:
            errors=np.array([r[method+'_error'] for r in block])
            out.update({method+'_mae':float(errors.mean()),method+'_error_sd':float(errors.std(ddof=1)),
                        method+'_max_error':float(errors.max()),
                        method+'_mean_R':float(np.mean([r[method+'_R'] for r in block]))})
        output.append(out)
    return output


def measure(image,angle,config,**meta):
    result=analyze(image,config)
    row=dict(meta);row['angle_true']=angle
    for method,s in [('spatial',result.spatial_stats),('fourier',result.fourier_stats)]:
        row.update({method+'_angle':s['peak_angle_deg'],method+'_error':axial_error(s['peak_angle_deg'],angle),
                    method+'_R':s['resultant_length'],method+'_entropy':s['entropy_normalized']})
    return row


def run_experiments(directory: str | Path):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    figures=directory/'figures';figures.mkdir(exist_ok=True)
    config=AnalysisConfig()
    cv2.setNumThreads(1)
    rows=[]
    for noise in NOISE_LEVELS:
        for angle in ANGLES:
            for seed in SEEDS:
                image=quantized(stripes(angle,noise=noise,seed=seed))
                rows.append(measure(image,angle,config,noise_sigma=noise,seed=seed))
    save_csv(directory/'accuracy.csv',rows)
    accuracy=summarize(rows,'noise_sigma');save_csv(directory/'accuracy_summary.csv',accuracy)
    for field,ylabel,name in [('mae','Mean axial error (degrees)','accuracy_vs_noise.png'),
                             ('mean_R','Mean axial resultant R','resultant_vs_noise.png')]:
        fig,ax=plt.subplots(figsize=(7.5,4.1))
        for method,label in [('spatial','Sobel'),('fourier','Fourier')]:
            ax.plot(NOISE_LEVELS,[r[f'{method}_{field}'] for r in accuracy],marker='o',label=label)
        ax.set(xlabel='Noise standard deviation before clipping [0,1]',ylabel=ylabel,
               title='12 orientations x 5 seeds per noise level')
        ax.grid(alpha=.25);ax.legend();save_plot(fig,figures/name)
    sigma_rows=[]
    for sigma in [0.,.5,1.,2.]:
        for angle in ANGLES:
            for seed in range(3):
                sigma_rows.append(measure(quantized(stripes(angle,noise=.15,seed=seed)),angle,
                    replace(config,gaussian_sigma=sigma),sigma=sigma,seed=seed))
    save_csv(directory/'ablation_sigma.csv',sigma_rows)
    sigma_summary=summarize(sigma_rows,'sigma');save_csv(directory/'ablation_sigma_summary.csv',sigma_summary)
    fig,ax=plt.subplots(figsize=(7.5,4.1))
    for method,label in [('spatial','Sobel'),('fourier','Fourier')]:
        ax.plot([r['sigma'] for r in sigma_summary],[r[method+'_mae'] for r in sigma_summary],marker='o',label=label)
    ax.set(xlabel='Gaussian sigma (pixels)',ylabel='Mean axial error (degrees)',title='Ablation: Gaussian preprocessing; noise sigma = 0.15')
    ax.grid(alpha=.25);ax.legend();save_plot(fig,figures/'sigma_ablation.png')
    bin_rows=[]
    # Off-grid angles keep the bin-count comparison from favoring exact bin centers.
    for bins in [36,90,180,360]:
        for angle in [a+7 for a in ANGLES]:
            for seed in range(3):
                bin_rows.append(measure(quantized(stripes(angle,noise=.15,seed=seed)),angle,
                    replace(config,bins=bins),bins=bins,seed=seed))
    save_csv(directory/'ablation_bins.csv',bin_rows)
    bin_summary=summarize(bin_rows,'bins');save_csv(directory/'ablation_bins_summary.csv',bin_summary)
    window_rows=[]
    for hann in [False,True]:
        for angle in [a+7 for a in ANGLES]:
            for seed in range(3):
                window_rows.append(measure(quantized(stripes(angle,noise=.15,seed=seed)),angle,
                    replace(config,use_hann=hann),hann=int(hann),seed=seed))
    save_csv(directory/'ablation_hann.csv',window_rows)
    window_summary=summarize(window_rows,'hann');save_csv(directory/'ablation_hann_summary.csv',window_summary)
    runtime=[]
    for size in [128,256,512,1024]:
        image=quantized(stripes(30,(size,size),noise=.15,seed=2026))
        analyze(image,config)
        timings=[]
        for _ in range(5):
            t=perf_counter();analyze(image,config);timings.append((perf_counter()-t)*1000)
        runtime.append({'size':size,'n_runs':5,'median_ms':float(np.median(timings)),
                        'min_ms':float(min(timings)),'max_ms':float(max(timings))})
    save_csv(directory/'runtime.csv',runtime)
    fig,ax=plt.subplots(figsize=(7.5,4.1))
    ax.plot([r['size'] for r in runtime],[r['median_ms'] for r in runtime],marker='o')
    ax.set(xlabel='Square image side (pixels)',ylabel='Median analysis time (ms)',
           title='CPU analysis only; 5 runs after warm-up; excludes image export')
    ax.grid(alpha=.25);save_plot(fig,figures/'runtime.png')
    root=Path(__file__).resolve().parents[1]
    samples=root/'data/samples';generate_samples(samples)
    cases={}
    selected=['stripes_030.png','stripes_030_noise015.png','crossing_030_120.png',
              'white_noise.png','constant.png','two_regions_020_070.png','rectangular_035.png']
    for filename in selected:
        result=analyze(load_image(samples/filename),config)
        cases[filename]=result.summary()
        write_export(result,directory/'cases'/Path(filename).stem,filename)
    # Analyze individual ROIs from the nonstationary example as a contrast to
    # global analysis. The dividing boundary is not included in either ROI.
    mixed=load_image(samples/'two_regions_020_070.png')
    cases['roi_left']=analyze(mixed,config,roi=(8,8,112,240)).summary()
    cases['roi_right']=analyze(mixed,config,roi=(136,8,112,240)).summary()
    environment={'python':platform.python_version(),'platform':platform.platform(),
                 'opencv_threads':cv2.getNumThreads(),'seed_list':SEEDS}
    for dist in ['numpy','scipy','opencv-python-headless','opencv-python','matplotlib','Pillow','pytest']:
        try:environment[dist]=importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:pass
    try:
        cpu=[line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')]
        if cpu:environment['cpu']=cpu[0]
    except OSError:pass
    summary={'design':{'angles_deg':ANGLES,'noise_sigmas':NOISE_LEVELS,'seeds':SEEDS,
                       'shape':[256,256],'period_px':16,'amplitude':.35,'offset':.5,
                       'phase_rad':.37,'quantization':'clip [0,1], round to uint8 before analysis',
                       'accuracy_images':len(rows),'sigma_ablation_images':len(sigma_rows),
                       'bins_ablation_images':len(bin_rows),'hann_ablation_images':len(window_rows)},
             'config':asdict(config),'accuracy':accuracy,'sigma_ablation':sigma_summary,
             'bins_ablation':bin_summary,'hann_ablation':window_summary,'runtime':runtime,
             'cases':cases,'environment':environment,
             'fiji_plugin_execution':'Separate reference run: results/fiji/settings.txt; this command executes Python only.'}
    (directory/'metrics.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ['design','accuracy','sigma_ablation','bins_ablation','hann_ablation','runtime']},indent=2))
    print(f'Experiment artifacts saved to {directory}')
    return summary
