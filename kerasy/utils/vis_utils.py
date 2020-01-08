# coding: utf-8
import copy
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from mpl_toolkits.mplot3d import Axes3D

from .generic_utils import handleKeyError

def galleryplot(func, argnames, iterator, ncols=5, figsize=(4,4), sharex="none", sharey="none", **kwargs):

    """Plot many figures as a gallery.

    Parameters
    ----------
    @param func         : function which plots each image. NOTE: they must recieve the Axes object.
    @param argnames     : keys of one or more arguments. These are given to `func`.
    @param iterator     : iterator which has one or more values, or zip object of them.
    @param ncols        : number of images arranged horizontally (x-axis).
    @param figsize      : (Widht, Height). image size of each image.
    @param sharex,sharey: bool or {'none', 'all', 'row', 'col'}
    @return fig         : class `matplotlib.figure.Figure` object.
    @return axes        : Axes object or array of Axes objects.

    Examples
    --------
    [1-argument]
    >>> def sample(ax, color):
            ax.scatter(0,0,color=color,s=500)
            return ax
    >>> colors=["red","blue","green","black"]
    >>> fig, axes = galleryplot(func=sample, argnames="color", iterator=colors, ncols=4)
    >>> plt.tight_layout()
    >>> plt.show()

    [multi-args]
    >>> def sample(ax, color, marker):
        ax.scatter(0,0,color=color,s=500, marker=marker)
        return ax
    >>> colors  = ["red","blue","green","black"]
    >>> markers = ["o","s","x","^"]
    >>> fig, axes = galleryplot(func=sample2, argnames=["color","marker"], iterator=zip(colors,markers), ncols=4)
    >>> plt.tight_layout()
    >>> plt.show()
    """

    W,H = figsize
    iter_for_count = copy.deepcopy(iterator)
    nfigs = len([e for e in iter_for_count])
    nrows = nfigs//ncols if nfigs%ncols==0 else nfigs//ncols+1
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, sharex=sharex, sharey=sharey, figsize=(W*ncols, H*nrows))
    axes = axes if axes.ndim>1 else axes.reshape(1,-1)
    for i,vals in enumerate(iterator):
        kwargs = {argnames:vals} if isinstance(argnames, str) else dict(zip(argnames,vals))
        ax = func(ax=axes[i//ncols, i%ncols], **kwargs)

    return fig, axes

def plot_2D(*data, ax=None, figsize=(4,4), **plotargs):
    """ visualize 2-dimensional data. """
    if ax is None: fig, ax = plt.subplots(figsize=figsize)

    if len(data)==1:
        x = data[0]
        y = np.zeros(shape=len(x))
        label = False
    elif len(data)==2:
        x,y = data
        label = True
    else:
        raise ValueError(f"When passing data, it must contain 1 (only data) or 2 (data, class_label) items. However, it contains {len(data)} items.")
    n_cls = len(np.unique(y))
    for cls in np.unique(y):
        ax.scatter(x[y==cls, 0], x[y==cls, 1], label=f"cls.{cls}" if label else None, color=cm.jet(cls/n_cls))
    ax.set_xlabel("$x$", fontsize=14), ax.set_ylabel("$y$", fontsize=14)
    return ax

def objVSexp(obj, *exp, **options):
    """ Visualize 'Objective variable' vs. 'Explanatory variable' plot.
    @params
    @params var_type: str, 'continuous' or 'discrete' (default='continuous')
    """   
    n_features = len(exp)
    if n_features==0 or n_features>3:
        raise ValueError(f"The number of explanatory variables should be 1 or 2, but {n_features}")
        
    var_type = options.pop("var_type", "continuous")
    figsize  = options.pop("figsize", None)
    ax       = options.pop("ax", None)
    color    = options.pop("color", "#722f37")
    alpha    = options.pop("alpha", .2)
    handleKeyError(["continuous", "discrete"], var_type=var_type)
        
    if ax is None:
        fig = plt.figure(figsize=figsize)
        projection = None if n_features==1 else "3d"
        ax = fig.add_subplot(1,1,1,projection=projection)

    if n_features==1:
        if var_type=="continuous":
            ax.scatter(*exp, obj, color=color, alpha=alpha)
        else:
            sns.boxplot(*exp, obj, ax=ax)
    else:
        ax.scatter(*exp, obj, color=color, alpha=alpha)
        
    return ax
