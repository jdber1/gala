# Third-party
import astropy.units as u
import astropy.coordinates as coord
from astropy.coordinates.transformations import (DynamicMatrixTransform,
                                                 FunctionTransform)
from astropy.coordinates.attributes import (CoordinateAttribute,
                                            QuantityAttribute)
from astropy.coordinates.matrix_utilities import (rotation_matrix,
                                                  matrix_product,
                                                  matrix_transpose)
import numpy as np


def greatcircle_to_greatcircle(from_greatcircle_coord,
                               to_greatcircle_frame):
    """Transform between two greatcircle frames."""

    # This transform goes through the parent frames on each side.
    # from_frame -> from_frame.origin -> to_frame.origin -> to_frame
    intermediate_from = from_greatcircle_coord.transform_to(
        from_greatcircle_coord.pole)
    intermediate_to = intermediate_from.transform_to(
        to_greatcircle_frame.pole)
    return intermediate_to.transform_to(to_greatcircle_frame)


def reference_to_greatcircle(reference_frame, greatcircle_frame):
    """Convert a reference coordinate to a great circle frame."""

    # Define rotation matrices along the position angle vector, and
    # relative to the origin.
    pole = greatcircle_frame.pole.transform_to(coord.ICRS)
    ra0 = greatcircle_frame.ra0

    R_rot = rotation_matrix(greatcircle_frame.rotation, 'z')

    xaxis = np.array([np.cos(ra0), np.sin(ra0), 0.])
    zaxis = pole.cartesian.xyz.value
    xaxis[2] = -(zaxis[0]*xaxis[0] + zaxis[1]*xaxis[1]) / zaxis[2] # what?
    xaxis = xaxis / np.sqrt(np.sum(xaxis**2))
    yaxis = np.cross(zaxis, xaxis)
    R = np.stack((xaxis, yaxis, zaxis))

    return matrix_product(R_rot, R)


def greatcircle_to_reference(greatcircle_coord, reference_frame):
    """Convert an great circle frame coordinate to the reference frame"""

    # use the forward transform, but just invert it
    R = reference_to_greatcircle(reference_frame, greatcircle_coord)
    # transpose is the inverse because R is a rotation matrix
    return matrix_transpose(R)


def greatcircle_transforms(self_transform=False):
    def set_greatcircle_transforms(cls):
        DynamicMatrixTransform(reference_to_greatcircle,
                               coord.ICRS, cls,
                               register_graph=coord.frame_transform_graph)

        DynamicMatrixTransform(greatcircle_to_reference,
                               cls, coord.ICRS,
                               register_graph=coord.frame_transform_graph)

        if self_transform:
            FunctionTransform(greatcircle_to_greatcircle,
                              cls, cls,
                              register_graph=coord.frame_transform_graph)
        return cls

    return set_greatcircle_transforms


@greatcircle_transforms(self_transform=True)
class GreatCircleICRSFrame(coord.BaseCoordinateFrame):
    """A frame rotated into great circle coordinates with the pole and longitude
    specified as frame attributes.

    ``GreatCircleFrame``s always have component names for spherical coordinates
    of ``phi1``/``phi2``.

    Parameters
    ----------
    phi1 : `~astropy.units.Quantity`
        Longitude component.
    phi2 : `~astropy.units.Quantity`
        Latitude component.
    distance : `~astropy.units.Quantity`
        Distance.

    pm_phi1_cosphi2 : `~astropy.units.Quantity`
        Proper motion in longitude.
    pm_phi2 : `~astropy.units.Quantity`
        Proper motion in latitude.
    radial_velocity : `~astropy.units.Quantity`
        Line-of-sight or radial velocity.

    Frame attributes
    ----------------
    pole : `~astropy.coordinates.SkyCoord`, `~astropy.coordinates.ICRS`
        The coordinate specifying the pole of this frame.
    ra0 : `~astropy.coordinates.Angle`, `~astropy.units.Quantity` [angle]
        The right ascension (RA) of the zero point of the longitude of this
        frame.
    rotation : `~astropy.coordinates.Angle`, `~astropy.units.Quantity` [angle]
        The final rotation of the frame about the pole.

    """

    pole = CoordinateAttribute(default=None, frame=coord.ICRS)
    ra0 = QuantityAttribute(default=0, unit=u.deg)
    rotation = QuantityAttribute(default=0, unit=u.deg)

    frame_specific_representation_info = {
        coord.SphericalRepresentation: [
            coord.RepresentationMapping('lon', 'phi1'),
            coord.RepresentationMapping('lat', 'phi2'),
            coord.RepresentationMapping('distance', 'distance')]
    }

    default_representation = coord.SphericalRepresentation
    default_differential = coord.SphericalCosLatDifferential

    _default_wrap_angle = 180*u.deg

    def __init__(self, *args, **kwargs):
        wrap = kwargs.pop('wrap_longitude', True)
        super().__init__(*args, **kwargs)
        if wrap and isinstance(self._data, (coord.UnitSphericalRepresentation,
                                            coord.SphericalRepresentation)):
            self._data.lon.wrap_angle = self._default_wrap_angle
