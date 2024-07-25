import json
import math
import os
import random
import sys
from collections.abc import Generator

import pygame
import pygame.gfxdraw
import pytmx

from src import settings
from src.enums import Direction
from src.settings import (
    CHAR_TILE_SIZE,
    SCALE_FACTOR,
    TILE_SIZE, SCALED_TILE_SIZE,
)


def resource_path(relative_path: str):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    relative_path = relative_path.replace("/", os.sep)
    try:
        base_path = sys._MEIPASS  # noqa
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base_path, relative_path)


# Might be changed later on if we use pygame.freetype instead
def import_font(size: int, font_path: str) -> pygame.font.Font:
    return pygame.font.Font(resource_path(font_path), size)


def import_image(img_path: str, alpha: bool = True) -> pygame.Surface:
    full_path = resource_path(img_path)
    surf = pygame.image.load(full_path).convert_alpha(
    ) if alpha else pygame.image.load(full_path).convert()
    return pygame.transform.scale_by(surf, SCALE_FACTOR)


def import_folder(fold_path: str) -> list[pygame.Surface]:
    frames = []
    for folder_path, _, file_names in os.walk(resource_path(fold_path)):
        for file_name in sorted(
            file_names, key=lambda name: int(
                name.split('.')[0])):
            full_path = os.path.join(folder_path, file_name)
            frames.append(pygame.transform.scale_by(
                pygame.image.load(full_path).convert_alpha(), SCALE_FACTOR))
    return frames


def import_folder_dict(fold_path: str) -> dict[str, pygame.Surface]:
    frames = {}
    for folder_path, _, file_names in os.walk(resource_path(fold_path)):
        for file_name in file_names:
            full_path = os.path.join(folder_path, file_name)
            frames[file_name.split('.')[0]] = pygame.transform.scale_by(
                pygame.image.load(full_path).convert_alpha(), SCALE_FACTOR)
    return frames


def tmx_importer(tmx_path: str) -> settings.MapDict:
    files = {}
    for folder_path, _, file_names in os.walk(resource_path(tmx_path)):
        for file_name in file_names:
            full_path = os.path.join(folder_path, file_name)
            files[file_name.split('.')[0]] = (
                pytmx.util_pygame.load_pygame(full_path)
            )
    return files


def animation_importer(*ani_path: str, frame_size: int = None, resize: int = None) -> settings.AniFrames:
    if frame_size is None:
        frame_size = TILE_SIZE

    animation_dict = {}
    for folder_path, _, file_names in os.walk(os.path.join(*ani_path)):
        for file_name in file_names:
            full_path = os.path.join(folder_path, file_name)
            surf = pygame.image.load(full_path).convert_alpha()
            animation_dict[str(file_name.split('.')[0])] = []
            for col in range(surf.get_width() // frame_size):
                cutout_surf = pygame.Surface(
                    (frame_size, frame_size), pygame.SRCALPHA)
                cutout_rect = pygame.Rect(
                    col * frame_size, 0, frame_size, frame_size)
                cutout_surf.blit(surf, (0, 0), cutout_rect)

                if resize:
                    animation_dict[str(file_name.split('.')[0])].append(
                        pygame.transform.scale(cutout_surf, (resize, resize))
                    )
                else:
                    animation_dict[str(file_name.split('.')[0])].append(
                        pygame.transform.scale_by(cutout_surf, SCALE_FACTOR)
                    )

    return animation_dict


def _single_file_importer(
        *sc_path: str, size: int, directions: list[str]
) -> settings.AniFrames:
    char_dict = {}
    full_path = os.path.join(*sc_path)
    surf = pygame.image.load(full_path).convert_alpha()
    for row, dirct in enumerate(directions):
        char_dict[dirct] = []
        for col in range(surf.get_width() // size):
            cutout_surf = pygame.Surface((size, size), pygame.SRCALPHA)
            cutout_rect = pygame.Rect(
                col * size,
                row * size,
                size,
                size)
            cutout_surf.blit(surf, (0, 0), cutout_rect)
            char_dict[dirct].append(
                pygame.transform.scale_by(cutout_surf, SCALE_FACTOR))

    if "left" in directions and "right" not in directions:
        char_dict['right'] = [pygame.transform.flip(
            surf, True, False) for surf in char_dict['left']]
    elif "right" in directions and "left" not in directions:
        char_dict['left'] = [pygame.transform.flip(
            surf, True, False) for surf in char_dict['right']]
    return char_dict


def _single_folder_importer(path: str, size: int, directions: list[Direction]):
    folder = {}
    for folder_path, sub_folders, file_names in os.walk(path):
        for file_name in file_names:
            folder[file_name.split('.')[0]] = (
                _single_file_importer(
                    os.path.join(folder_path, file_name),
                    size=size,
                    directions=directions,
                )
            )
    return folder


def entity_importer(
        chr_path: str, size: int, directions: list[Direction]
) -> dict[str, settings.AniFrames]:
    # create dict with subfolders
    char_dict = {}
    for _, sub_folders, _ in os.walk(resource_path(chr_path)):
        if sub_folders:
            char_dict = {folder: {} for folder in sub_folders}

    if char_dict:
        # go through all found characters
        # and use _single_folder_importer to get their frames
        for char, frame_dict in char_dict.items():
            char_dict[char] = _single_folder_importer(
                os.path.join(resource_path(chr_path), char),
                size=size,
                directions=directions
            )
    else:
        # import the frames of a single character
        char_dict = _single_folder_importer(
            resource_path(chr_path),
            size=size,
            directions=directions
        )
    return char_dict


def sound_importer(
        *snd_path: str,
        default_volume: float = 0.5
        ) -> settings.SoundDict:
    sounds_dict = {}

    for sound_name in os.listdir(resource_path(os.path.join(*snd_path))):
        key = sound_name.split('.')[0]
        value = pygame.mixer.Sound(os.path.join(*snd_path, sound_name))
        value.set_volume(default_volume)
        sounds_dict[key] = value
    return sounds_dict


def save_data(data, file_name):
    folder_path = resource_path('data/settings')
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    with open(resource_path('data/settings/' + file_name), 'w') as file:
        json.dump(data, file, indent=4)


def load_data(file_name):
    with open(resource_path('data/settings/' + file_name), 'r') as file:
        return json.load(file)


def map_coords_to_tile(pos):
    return (pos[0] // SCALED_TILE_SIZE,
            pos[1] // SCALED_TILE_SIZE)


def generate_particle_surf(img: pygame.Surface) -> pygame.Surface:
    px_mask = pygame.mask.from_surface(img)
    ret = px_mask.to_surface()
    ret.set_colorkey("black")
    return ret


def flip_items(d: dict) -> dict:
    """Returns a copy of d with key-value pairs flipped (i.e. keys become values and vice-versa)."""
    ret = {}
    for key, val in d.items():
        ret[val] = key
    return ret


def tile_to_screen(pos):
    tile_size = TILE_SIZE * SCALE_FACTOR
    return pos[0] * tile_size, pos[1] * tile_size


def screen_to_tile(pos):
    tile_size = TILE_SIZE * SCALE_FACTOR
    return pos[0] // tile_size, pos[1] // tile_size


def get_flight_matrix(
        pos: tuple[int, int], radius: int, angle: float = math.pi / 2
) -> list[list[int]]:
    """
    Returns a matrix with the width and height of radius * 2 + 1, with a value
    of 1 if the matrix position can be fled to and 0 if not.
    The position from which the flight is to be started is always in the centre
    of the matrix. The position of the object to be fled from should be
    relative to the start position, but does not have to be within the
    matrix coordinates.

    TODO: Could be optimised so that instead of a matrix with integer / boolean
     values a matrix with the weight of each possible position is returned, of
     which the walkable position with the greatest weight is then fled to.

    :param pos: Position of the object that should be fled from
    :param radius: Radius / distance of the flight vector.
                   The returned matrix has a width and height of radius * 2 + 1
    :param angle: Angle of the flight vector (measured in radians)
                  Default: PI / 2 (90°)
    :return: Matrix with positions that can be fled to
    """

    diameter = radius * 2 + 1

    p1 = (radius, radius)
    p2 = (pos[0] + radius, pos[1] + radius)

    matrix = [[0 for _ in range(diameter)] for _ in range(diameter)]

    # For further calculations the angle gets inverted and divided by two
    # Can probably be optimised
    angle = math.pi - angle / 2

    # The exact angle of the position that should be fled from, measured from
    # the centre of the matrix
    dangerous_angle = math.atan2(
        (p1[0] - p2[0]),
        (p1[1] - p2[1])
    )

    for y in range(len(matrix)):
        for x in range(len(matrix[0])):
            # Angle from the centre of the matrix to the currently checked pos
            current_angle = math.atan2(
                (p1[0] - x),
                (p1[1] - y)
            )
            # Angular distance of the dangerous angle and the current angle
            distance = dangerous_angle - current_angle

            # Distance could be greater than half a turn,
            # in which case the result is rotated to the other extreme
            if distance > math.pi:
                distance = distance - (math.pi * 2)
            elif distance < -math.pi:
                distance = distance + (math.pi * 2)

            if -angle < distance < angle:
                matrix[y][x] = 0
            else:
                matrix[y][x] = 1

    return matrix


def draw_aa_line(
        surface: pygame.Surface,
        center_pos: tuple[float, float],
        thickness: int,
        length: int,
        deg: float,
        color: tuple[int, int, int],
):
        ul = (center_pos[0] + (length / 2.) * math.cos(deg) - (thickness / 2.) * math.sin(deg),
              center_pos[1] + (thickness / 2.) * math.cos(deg) + (length / 2.) * math.sin(deg))
        ur = (center_pos[0] - (length / 2.) * math.cos(deg) - (thickness / 2.) * math.sin(deg),
              center_pos[1] + (thickness / 2.) * math.cos(deg) - (length / 2.) * math.sin(deg))
        bl = (center_pos[0] + (length / 2.) * math.cos(deg) + (thickness / 2.) * math.sin(deg),
              center_pos[1] - (thickness / 2.) * math.cos(deg) + (length / 2.) * math.sin(deg))
        br = (center_pos[0] - (length / 2.) * math.cos(deg) + (thickness / 2.) * math.sin(deg),
              center_pos[1] - (thickness / 2.) * math.cos(deg) - (length / 2.) * math.sin(deg))

        pygame.gfxdraw.aapolygon(surface, (ul, ur, br, bl), color)
        pygame.gfxdraw.filled_polygon(surface, (ul, ur, br, bl), color)


def get_entity_facing_direction(
        direction: tuple[float, float] | pygame.math.Vector2,
        default_value: Direction = Direction.RIGHT
) -> Direction:
    """
    :param direction: Direction to use.
    :param default_value: Default direction to use.
    :return: String of the direction the entity is facing
    """
    # prioritizes vertical animations, flip if statements to get horizontal
    # ones
    if direction[0]:
        return Direction.RIGHT if direction[0] > 0 else Direction.LEFT
    if direction[1]:
        return Direction.DOWN if direction[1] > 0 else Direction.UP
    return default_value


def near_tiles(
        pos: tuple[int, int], radius: int, shuffle: bool = False
) -> Generator[tuple[int, int], None, None]:
    """
    :param pos: The centre of the generated positions
    :param radius: The radius of the square
    :param shuffle: Whether the positions should be yielded in a random order
    :return: Generator for all positions within a square of the width and
    height of radius * 2 + 1 around the given position
    """
    horizontal = list(range(radius * 2 + 1))
    vertical = list(range(radius * 2 + 1))

    horizontal.pop(radius)
    vertical.pop(radius)

    if shuffle:
        random.shuffle(horizontal)
        random.shuffle(vertical)

    for i in horizontal:
        for j in vertical:
            yield int(pos[0] - radius + i), int(pos[1] - radius + j)
