# -*- coding: UTF-8 -*-
#
# Copyright (C) 2024, Team Kodi
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Replacement for the old web-scraping IMDb ratings module.
# Now uses local IMDb dataset (SQLite) for ratings and genres.

from . import get_imdb_id
from . import imdb_dataset


def get_details(uniqueids):
    """Get IMDb rating from the local dataset cache.

    Returns dict with 'ratings' key (and optionally 'info' with genres).
    """
    imdb_id = get_imdb_id(uniqueids)
    if not imdb_id:
        return {}

    result = {}
    rating_data = imdb_dataset.get_rating(imdb_id)
    if rating_data:
        result['ratings'] = {
            'imdb': {
                'votes': rating_data['votes'],
                'rating': rating_data['rating']
            }
        }
    return result
