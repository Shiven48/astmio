#
# Copyright (C) 2013 Alexander Shorin
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

#: ASTM specification base encoding.
ENCODING = "latin-1"

#: Message start token.
STX = b"\x02"
#: Message end token.
ETX = b"\x03"
#: ASTM session termination token.
EOT = b"\x04"
#: ASTM session initialization token.
ENQ = b"\x05"
#: Command accepted token.
ACK = b"\x06"
#: Command rejected token.
NAK = b"\x15"
#: Message chunk end token.
ETB = b"\x17"
LF = b"\x0a"
CR = b"\x0d"
#: CR + LF shortcut.
CRLF = CR + LF

#: Message records delimiter.
RECORD_SEP = b"\x0d"  # \r #
#: Record fields delimiter.
FIELD_SEP = b"\x7c"  # |  #
#: Delimeter for repeated fields.
REPEAT_SEP = b"\x5c"  # \  #
#: Field components delimiter.
COMPONENT_SEP = b"\x5e"  # ^  #
#: Date escape token.
ESCAPE_SEP = b"\x26"  # &  #
# Valid astm record types
DEFAULT_VALID_RECORD_TYPES = {
    b"H",
    b"P",
    b"O",
    b"R",
    b"L",
    b"Q",
    b"M",
    b"S",
    b"C",
}
# legal range for an astm frame number if range > 7 wrap around and start with 1
DEFAULT_FRAME_RANGE = range(1, 8)
