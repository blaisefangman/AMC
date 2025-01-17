# -*- coding: ISO-8859-1 -*-
#
#
# Copyright (C) 2004-2005 Andr� Wobst <wobsta@users.sourceforge.net>
#
# This file is part of PyX (http://pyx.sourceforge.net/).
#
# PyX is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# PyX is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PyX; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA


__allmodules__ = ["data", "key", "style", "axis"]
for module in __allmodules__:
    __import__(module, globals(), locals(), [])

from . import graph
__allgraph__ = ["graphxy", "graphxyz"]
for importfromgraph in __allgraph__:
    locals()[importfromgraph] = getattr(graph, importfromgraph)

__all__ = __allmodules__ + __allgraph__
