import os
from os.path import join as pjoin

import numpy as np
from scipy import stats

from . import io
from .io import Surface

lh_viewdict = {'lateral': (180, 90),
                'medial': (0, 90),
                'anterior': (90, 90),
                'posterior': (-90, 90),
                'dorsal': (90, 0),
                'ventral': (-90, 180)}
rh_viewdict = {'lateral': (0, 90),
                'medial': (0, -90),
                'anterior': (90, 90),
                'posterior': (-90, -90),
                'dorsal': (-90, 0),
                'ventral': (90, 0)}


class Brain(object):
    """Brain object for visualizing with mlab."""

    def __init__(self, subject_id, hemi, surf, curv=True):
        """Initialize a Brain object with Freesurfer-specific data.

        Parameters
        ----------
        subject_id : str
            subject name in Freesurfer subjects dir
        hemi : str
            hemisphere id (ie 'lh' or 'rh')
        surf :  geometry name
            freesurfer surface mesh name (ie 'white', 'inflated', etc.)
        curv : boolean
            if true, loads curv file and displays binary curvature
            (default: True)
        """
        from enthought.mayavi import mlab

        # Set the identifying info
        self.subject_id = subject_id
        self.hemi = hemi
        if self.hemi == 'lh':
            self.viewdict = lh_viewdict
        elif self.hemi == 'rh':
            self.viewdict = rh_viewdict
        self.surf = surf

        # Initialize an mlab figure
        self._f = mlab.figure(np.random.randint(1, 1000),
                              bgcolor=(12. / 256, 0. / 256, 25. / 256),
                              size=(800, 800))
        mlab.clf()
        self._f.scene.disable_render = True

        # Initialize a Surface object as the geometry
        self._geo = Surface(subject_id, hemi, surf)

        # Load in the geometry and (maybe) curvature
        self._geo.load_geometry()
        if curv:
            self._geo.load_curvature()
            curv_data = self._geo.bin_curv
            meshargs = dict(scalars=curv_data)
        else:
            curv_data = None
            meshargs = dict()

        # mlab pipeline mesh for geomtery
        self._geo_mesh = mlab.pipeline.triangular_mesh_source(
                                        self._geo.x, self._geo.y, self._geo.z,
                                        self._geo.faces, **meshargs)

        # mlab surface for the geometry
        if curv:
            colormap, vmin, vmax, reverse = self.__get_geo_colors()
            self._geo_surf = mlab.pipeline.surface(self._geo_mesh,
                                colormap=colormap, vmin=vmin, vmax=vmax)
            if reverse:
                curv_bar = mlab.scalarbar(self._geo_surf)
                curv_bar.reverse_lut = True
                curv_bar.visible = False
        else:
            self._geo_surf = mlab.pipeline.surface(self._geo_mesh,
                                                   color=(.5, .5, .5))

        # Initialize the overlay and morphometry dictionaries
        self.overlays = dict()
        self.morphometry = dict()

        # Turn disable render off so that it displays
        self._f.scene.disable_render = False

        # Bring up the lateral view
        self.show_view("lat")

    def show_view(self, view):
        """Orient camera to display view

        Parameters
        ----------
        view : {'lateral' | 'medial' | 'anterior' |
                'posterior' | 'superior' | 'inferior' | tuple}
            brain surface to view, or tuple to pass to mlab.view()
        """
        from enthought.mayavi import mlab

        if isinstance(view, str):
            if not view in self.viewdict:
                try:
                    view = self.__xfm_view(view)
                    mlab.view(*self.viewdict[view])
                except ValueError:
                    print("Cannot display %s view. Must be preset view "
                          "name or leading substring" % view)
        elif isinstance(view, tuple):
            mlab.view(*view)
        else:
            raise ValueError("View must be one of the preset view names "
                             "or a tuple to be passed to mlab.view()")

    def add_overlay(self, filepath, range=None, sign="abs",
                    name=None, visible=True):
        """Add an overlay to the overlay dict.

        Parameters
        ----------
        filepath : str
            path to the overlay file (must be readable by Nibabel, or .mgh
        range : (min, max)
            threshold and saturation point for overlay display
        sign : {'abs' | 'pos' | 'neg'}
            whether positive, negative, or both values should be displayed
        name : str
            name for the overlay in the internal dictionary
        visible : boolean
            whether the overlay should be visible upon load

        """
        if name is None:
            basename = os.path.basename(filepath)
            if basename.endswith(".gz"):
                basename = basename[:-3]
            name = os.path.splitext(basename)[0]

        if name in self.overlays:
            raise NameError("Overlay with name %s already exists. "
                            "Please provide a name for this overlay" % name)

        if not sign in ["abs", "pos", "neg"]:
            raise ValueError("Overlay sign must be 'abs', 'pos', or 'neg'")

        self._f.scene.disable_render = True
        scalar_data = io.read_scalar_data(filepath)
        self.overlays[name] = Overlay(scalar_data, self._geo, range, sign)
        self._f.scene.disable_render = False

    def add_morpometry(self, measure, visible=True):
        """Add a morphometry overlay to the image.

        Parameters
        ----------
        measure : {'area' | 'curv' | 'jacobian_white' | 'sulc' | 'thickness'}
            which measure to load
        visible : boolean
            whether the map should be visible upon load

        """
        from enthought.mayavi import mlab
        surf_dir = pjoin(os.environ['SUBJECTS_DIR'], self.subject_id, 'surf')
        morph_file = pjoin(surf_dir, '.'.join([self.hemi, measure]))
        if not os.path.exists(morph_file):
            raise ValueError(
                'Could not find %s in subject directory' % morph_file)

        cmap_dict = dict(area="pink",
                         curv="RdBu",
                         jacobian_white="pink",
                         sulc="RdBu",
                         thickness="pink")

        self._f.scene.disable_render = True
        morph_data = io.read_morph_data(morph_file)
        min = stats.scoreatpercentile(morph_data, 2)
        max = stats.scoreatpercentile(morph_data, 98)
        if morph_data.dtype.byteorder == '>':
            morph_data.byteswap(True)  # byte swap inplace; due to mayavi bug
        mesh = mlab.pipeline.triangular_mesh_source(self._geo.x,
                                                    self._geo.y,
                                                    self._geo.z,
                                                    self._geo.faces,
                                                    scalars=morph_data)
        surf = mlab.pipeline.surface(mesh, colormap=cmap_dict[measure],
                                     vmin=min, vmax=max,
                                     name=measure)
        bar = mlab.scalarbar(surf)
        self.morphometry[measure] = surf
        self._f.scene.disable_render = False

    def __get_geo_colors(self):
        """Return an mlab colormap name, vmin, and vmax for binary curvature.

        At the moment just return a default.  Get from the config eventually

        Returns
        -------
        colormap : string
            mlab colormap name
        vmin : float
            curv colormap minimum
        vmax : float
            curv colormap maximum
        reverse : boolean
            boolean indicating whether the colormap should be reversed

        """
        return "gray", -1., 2., True

    def save_image(self, fname):
        """Save current view to disk

        Only mayavi image types are supported:
        (png jpg bmp tiff ps eps pdf rib  oogl iv  vrml obj

        Parameters
        ----------
        filename: string
            path to new image file

        """
        from enthought.mayavi import mlab
        ftype = fname[fname.rfind('.') + 1:]
        good_ftypes = ['png', 'jpg', 'bmp', 'tiff', 'ps',
                        'eps', 'pdf', 'rib', 'oogl', 'iv', 'vrml', 'obj']
        if not ftype in good_ftypes:
            raise ValueError("Supported image types are %s"
                                % " ".join(good_ftypes))
        mlab.savefig(fname)

    def save_imageset(self, prefix, views, filetype='png'):
        """Convience wrapper for save_image

        Files created are prefix+'_$view'+filetype

        Parameters
        ----------
        prefix: string
            filename prefix for image to be created
        views: list
            desired views for images
        filetype: string
            image type

        Returns
        -------
        images_written: list
            all filenames written
        """
        if isinstance(views, basestring):
            raise ValueError("Views must be a non-string sequence"
                             "Use show_view & save_image for a single view")
        images_written = []
        for view in views:
            try:
                fname = "%s_%s.%s" % (prefix, view, filetype)
                images_written.append(fname)
                self.show_view(view)
                try:
                    self.save_image(fname)
                except ValueError:
                    print("Bad image type")
            except ValueError:
                print("Skipping %s: not in view dict" % view)
        return images_written

    def save_montage(self, filename, order=['lat', 'ven', 'med'], shape='h'):
        """Create a montage from a given order of images

        Parameters
        ----------
        filename: string
            path to final image
        order: list
            order of views to build montage
        shape: {'h' | 'v'}
            montage image shape

        """
        import Image
        fnames = self.save_imageset("tmp", order)
        images = map(Image.open, fnames)
        if shape == 'h':
            w = sum(i.size[0] for i in images)
            h = max(i.size[1] for i in images)
        else:
            h = sum(i.size[1] for i in images)
            w = max(i.size[0] for i in images)
        new = Image.new("RGBA", (w, h))
        x = 0
        for i in images:
            if shape == 'h':
                pos = (x, 0)
                x += i.size[0]
            else:
                pos = (0, x)
                x += i.size[1]
            new.paste(i, pos)
        try:
            new.save(filename)
        except Exception:
            print("Error saving %s" % filename)
        for f in fnames:
            os.remove(f)

    def __min_diff(self, beg, end):
        """Determine minimum "camera distance" between two views

        Parameters
        ----------
        beg: tuple
            beginning camera view
        end: tuple
            ending camera view

        Returns
        -------
        new_diff: np.array
            shortest camera "path" between two views

        """
        d = np.array(end) - np.array(beg)
        new_diff = []
        for x in d:
            if x > 180:
                new_diff.append(x - 360)
            elif x < -180:
                new_diff.append(x + 360)
            else:
                new_diff.append(x)
        return np.array(new_diff)

    def animate(self, views, n=180):
        """Animate a rotation

        Parameters
        ----------
        views: sequence
            views to animate through
        n: int
            number of steps to take in between
        save_gif: bool
            save the animation
        fname: string
            file to save gif image

        """
        import numpy as np
        from enthought.mayavi import mlab
        for i, v in enumerate(views):
            try:
                if isinstance(v, str):
                    b = self.__xfm_view(v, 't')
                end = views[i + 1]
                if isinstance(end, str):
                    e = self.__xfm_view(end, 't')
                d = self.__min_diff(b, e)
                dx = d / np.array((float(n)))
                ov = np.array(mlab.view(*b)[:2])
                for i in range(n):
                    nv = ov + i * dx
                    mlab.view(*nv)
            except IndexError:
                pass

    def __xfm_view(self, view, out='s'):
        """Normalize a given string to available view

        Parameters
        ----------
        view: string
            view which may match leading substring of available views

        Returns
        -------
        good: string
            matching view string
        out: {'s' | 't'}
            's' to return string, 't' to return tuple

        """
        if not view in self.viewdict:
            good_view = [k for k in self.viewdict if view == k[:len(view)]]
            if len(good_view) != 1:
                raise ValueError("bad view")
            view = good_view[0]
        if out == 't':
            return self.viewdict[view]
        else:
            return view


class Overlay(object):

    def __init__(self, scalar_data, geo, range, sign):
        """
        """
        from enthought.mayavi import mlab

        if scalar_data.min() >= 0:
            sign = "pos"
        elif scalar_data.max() <= 0:
            sign = "neg"

        if range is None:
            min = 2
            if sign == "neg":
                range_data = np.abs(scalar_data[np.where(scalar_data < 0)])
            elif sign == "pos":
                range_data = scalar_data[np.where(scalar_data > 0)]
            else:
                range_data = np.abs(scalar_data)
            max = stats.scoreatpercentile(range_data, 98)
        else:
            min, max = range

        # Byte swap inplace; due to mayavi bug
        mlab_data = scalar_data.copy()
        if scalar_data.dtype.byteorder == '>':
            mlab_data.byteswap(True)

        if sign in ["abs", "pos"]:
            pos_mesh = mlab.pipeline.triangular_mesh_source(geo.x,
                                                           geo.y,
                                                           geo.z,
                                                           geo.faces,
                                                           scalars=mlab_data)

            # Figure out the correct threshold to avoid TraitErrors
            # This seems like not the cleanest way to do this
            pos_data = scalar_data[np.where(scalar_data > 0)]
            try:
                pos_max = pos_data.max()
            except ValueError:
                pos_max = 0
            if pos_max < min:
                thresh_low = pos_max
            else:
                thresh_low = min
            pos_thresh = mlab.pipeline.threshold(pos_mesh, low=thresh_low)
            pos_surf = mlab.pipeline.surface(pos_thresh, colormap="YlOrRd",
                                             vmin=min, vmax=max)
            pos_bar = mlab.scalarbar(pos_surf)
            pos_bar.reverse_lut = True
            pos_bar.visible = False

            self.pos = pos_surf

        if sign in ["abs", "neg"]:
            neg_mesh = mlab.pipeline.triangular_mesh_source(geo.x,
                                                           geo.y,
                                                           geo.z,
                                                           geo.faces,
                                                           scalars=mlab_data)

            # Figure out the correct threshold to avoid TraitErrors
            # This seems even less clean due to negative convolutedness
            neg_data = scalar_data[np.where(scalar_data < 0)]
            try:
                neg_min = neg_data.min()
            except ValueError:
                neg_min = 0
            if neg_min > -min:
                thresh_up = neg_min
            else:
                thresh_up = -min
            neg_thresh = mlab.pipeline.threshold(neg_mesh, up=thresh_up)
            neg_surf = mlab.pipeline.surface(neg_thresh, colormap="Blues",
                                             vmin=-max, vmax=-min)

            self.neg = neg_surf