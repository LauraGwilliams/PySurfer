"""
Create movie from  MEG inverse solution
=======================================

Data were computed using mne-python (http://martinos.org/mne)

"""
print __doc__

import os
import numpy as np

from surfer import Brain
from surfer.io import read_stc

"""
create Brain object for visualization
"""
brain = Brain('fsaverage', 'split', 'inflated',
              config_opts=dict(width=800, height=400))

"""
read MNE dSPM inverse solution
"""
for hemi in ['lh', 'rh']:
    stc_fname = os.path.join('example_data',
                             'meg_source_estimate-' + hemi + '.stc')
    stc = read_stc(stc_fname)
    data = stc['data']

    """
    Calculate sample time points
    """
    times = np.arange(data.shape[1]) * stc['tstep'] + stc['tmin']

    brain.add_data(data, colormap='hot', vertices=stc['vertices'],
                   smoothing_steps=10, time=times, time_label='%0.3f s',
                   hemi=hemi)

"""
scale colormap
"""
brain.scale_data_colormap(fmin=13, fmid=18, fmax=22, transparent=True)

"""
Save movies with different combinations of views. Use a large value for
time_dilation because the sample stc only covers 30 ms
"""
brain.save_movie('example_current.mov', time_dilation=30)
brain.save_movie('example_single.mov', time_dilation=30, montage='single')
brain.save_movie('example_h.mov', time_dilation=30, montage=['lat', 'med'],
                 orientation='h')
brain.save_movie('example_v.mov', time_dilation=30, montage=[['lat'], ['med']])

brain.close()
