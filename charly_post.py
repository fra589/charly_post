# -*- coding: utf-8 -*-
# ***************************************************************************
# *   (c) sliptonic (shopinthewoods@gmail.com) 2014                         *
# *   (c) Gauthier Briere - 2018 - 2021                                     *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2.1 of   *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENSE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Lesser General Public License for more details.                   *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with This program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************/

import FreeCAD
from FreeCAD import Units
# Path scripts organization/path have been modified since FreeCAD 0.21
if (FreeCAD.Version()[0]+'.'+FreeCAD.Version()[1]) >= '0.21':
  import Path
  import Path.Base.Util as PathUtil
  import Path.Post.Utils as PostUtils
  import PathScripts.PathUtils as PathUtils
else:
  import Pacharly_post.pythScripts.PostUtils as PostUtils
import argparse
import datetime
import shlex


TOOLTIP = '''
Generate g-code from a Path that is compatible with the Charly robot.
import charly_post
charly_post.export(object,"/path/to/file.iso")
'''

# ***************************************************************************
# * Globals set customization preferences
# ***************************************************************************

# Default values for command line arguments:
OUTPUT_HEADER = True        # default output of comments in output gCode file
OUTPUT_COMMENTS = True      # default output header in output gCode file
OUTPUT_LINE_NUMBERS = True  # default does'nt utput lines numbers in output gCode file
SHOW_EDITOR = True          # default show the resulting file dialog output in GUI
PRECISION = 3               # Default precision for metric (see http://linuxcnc.org/docs/2.7/html/gcode/overview.html#_g_code_best_practices)
PREAMBLE = ''''''           # Preamble text will appear at the beginning of the GCODE output file.
POSTAMBLE = '''M5
M2
'''                         # Postamble text will appear following the last operation.

# Customisation with no command line argument
OUTPUT_TOOL_CHANGE = True
MODAL = True                # if true commands are suppressed if the same as previous line.
COMMAND_SPACE = " "
LINENR = 10                 # line number starting value
LINEINCR = 10
START_OR_M6 = True
DRILL_RETRACT_MODE = 'G98'  # Default value of drill retractations (OLD_Z) other possible value is G99
MOTION_MODE = 'G90'
UNITS = "G71"               # Les unités dans Charly robot sont gérées par G71 pour le metrique et G70 pour les pouces
UNIT_FORMAT = 'mm'
UNIT_SPEED_FORMAT = 'mm/min'

# ***************************************************************************
# * End of customization
# ***************************************************************************

parser = argparse.ArgumentParser(prog='grbl', add_help=False)
parser.add_argument('--header', action='store_true', help='output headers (default)')
parser.add_argument('--no-header', action='store_true', help='suppress header output')
parser.add_argument('--comments', action='store_true', help='output comment (default)')
parser.add_argument('--no-comments', action='store_true', help='suppress comment output')
parser.add_argument('--line-numbers', action='store_true', help='prefix with line numbers')
parser.add_argument('--no-line-numbers', action='store_true', help='don\'t prefix with line numbers (default)')
parser.add_argument('--show-editor', action='store_true', help='pop up editor before writing output (default)')
parser.add_argument('--no-show-editor', action='store_true', help='don\'t pop up editor before writing output')
parser.add_argument('--precision', default='3', help='number of digits of precision, default=3')
parser.add_argument('--preamble', help='set commands to be issued before the first command, default="G17\nG90"')
parser.add_argument('--postamble', help='set commands to be issued after the last command, default="M05\nG17 G90\n; M2"')

TOOLTIP_ARGS = parser.format_help()

# ***************************************************************************
# * Internal global variables
# ***************************************************************************


CURRENT_X = 0
CURRENT_Y = 0
CURRENT_Z = 0

CORNER_MIN = {'x': 0, 'y': 0, 'z': 0}
CORNER_MAX = {'x': 600, 'y': 420, 'z': 280}  # Pour Charly 2U (format A2)

# Commandes de mouvements
MOTION_COMMANDS = ['G0', 'G00', 'G1', 'G01', 'G2', 'G02', 'G3', 'G03']
RAPID_MOVES = ['G0', 'G00']

# liste des commandes modales
MODAL_COMMANDS = ['G0', 'G00', 'G1', 'G01']

# These commands are ignored by commenting them out
SUPPRESS_COMMANDS = ['G98', 'G99', 'G80', 'G17', 'G53', 'G54', 'G55', 'G56', 'G57', 'G58', 'G59']

# Pre operation text will be inserted before every operation
PRE_OPERATION = ''''''

# Post operation text will be inserted after every operation
POST_OPERATION = ''''''

# Tool Change commands will be inserted before a tool change
TOOL_CHANGE = ''''''

# to distinguish python built-in open function from the one declared below
if open.__module__ in ['__builtin__', 'io']:
    pythonopen = open


def processArguments(argstring):
    global OUTPUT_HEADER
    global OUTPUT_COMMENTS
    global OUTPUT_LINE_NUMBERS
    global SHOW_EDITOR
    global PRECISION
    global PREAMBLE
    global POSTAMBLE

    print(argstring)
    try:
        args = parser.parse_args(shlex.split(argstring))
        if args.no_header:
            OUTPUT_HEADER = False
        if args.header:
            OUTPUT_HEADER = True
        if args.no_comments:
            OUTPUT_COMMENTS = False
        if args.comments:
            OUTPUT_COMMENTS = True
        if args.no_line_numbers:
            OUTPUT_LINE_NUMBERS = False
        if args.line_numbers:
            OUTPUT_LINE_NUMBERS = True
        if args.no_show_editor:
            SHOW_EDITOR = False
        if args.show_editor:
            SHOW_EDITOR = True
        PRECISION = args.precision
        if args.preamble is not None:
            PREAMBLE = args.preamble
        if args.postamble is not None:
            POSTAMBLE = args.postamble
    except Exception as e:
        print("processArguments() error !")
        return False

    return True


def export(objectslist, filename, argstring):

    if not processArguments(argstring):
        return None

    global UNITS
    global UNIT_FORMAT
    global UNIT_SPEED_FORMAT
    global MOTION_MODE

    print("Post Processor: " + __name__ + " postprocessing...")
    gcode = ""

    # write header
    if OUTPUT_HEADER:
        gcode += linenumber() + "(Exported by FreeCAD)\n"
        gcode += linenumber() + "(Post Processor: " + __name__ + ")\n"
        gcode += linenumber() + "(Output Time: " + str(datetime.datetime.now()) + ")\n"

    # Write the preamble
    if OUTPUT_COMMENTS:
        gcode += linenumber() + "(begin preamble)\n"
    for line in PREAMBLE.splitlines(True):
        gcode += linenumber() + line
    gcode += linenumber() + UNITS + "\n"

    # verify if PREAMBLE have changed MOTION_MODE or UNITS
    if 'G90' in PREAMBLE:
        MOTION_MODE = 'G90'
    elif 'G91' in PREAMBLE:
        MOTION_MODE = 'G91'
    else:
        gcode += linenumber() + MOTION_MODE + "\n"
    if 'G71' in PREAMBLE:
        UNITS = 'G71'
        UNIT_FORMAT = 'mm'
        UNIT_SPEED_FORMAT = 'mm/min'
    elif 'G21' in PREAMBLE:
        UNITS = 'G71'
        UNIT_FORMAT = 'mm'
        UNIT_SPEED_FORMAT = 'mm/min'
    elif 'G70' in PREAMBLE:
        UNITS = 'G70'
        UNIT_FORMAT = 'in'
        UNIT_SPEED_FORMAT = 'in/min'
    elif 'G20' in PREAMBLE:
        UNITS = 'G70'
        UNIT_FORMAT = 'in'
        UNIT_SPEED_FORMAT = 'in/min'
    else:
        gcode += linenumber() + UNITS + "\n"

    for obj in objectslist:

        if not hasattr(obj, "Path"):
            print("Error : " + obj.Name + " is not a path. Please select only path and Compounds.")
            return

        # do the pre_op
        if OUTPUT_COMMENTS:
            gcode += linenumber() + "(begin operation: " + obj.Label + ")\n"
        for line in PRE_OPERATION.splitlines(True):
            gcode += linenumber() + line

        # Do the op
        gcode += parse(obj)

        # do the post_op
        if OUTPUT_COMMENTS:
            gcode += linenumber() + "(finish operation: " + obj.Label + ")\n"
        for line in POST_OPERATION.splitlines(True):
            gcode += linenumber() + line

    # do the post_amble
    if OUTPUT_COMMENTS:
        gcode += linenumber() + "(begin postamble)\n"
    for line in POSTAMBLE.splitlines(True):
        gcode += linenumber() + line

    # Show dialog result
    if FreeCAD.GuiUp and SHOW_EDITOR:
        dia = PostUtils.GCodeEditorDialog()
        dia.editor.setText(gcode)
        result = dia.exec_()
        if result:
            final = dia.editor.toPlainText()
        else:
            final = gcode
    else:
        final = gcode

    print("Done postprocessing.")

    # write the file
    gfile = pythonopen(filename, "w")
    gfile.write(final)
    gfile.close()


def linenumber():
    global LINENR
    global LINEINCR
    if OUTPUT_LINE_NUMBERS:
        s = "N" + str(LINENR) + " "
        LINENR += LINEINCR
        return s
    return ""


def format_outstring(strTbl):
    global COMMAND_SPACE
    # construct the line for the final output
    s = ""
    for w in strTbl:
        s += w + COMMAND_SPACE
    s = s.strip()
    return s


def parse(pathobj):

    global DRILL_RETRACT_MODE
    global MOTION_MODE
    global CURRENT_X
    global CURRENT_Y
    global CURRENT_Z
    global START_OR_M6
    x_ok = False
    y_ok = False
    z_ok = False
    out = ""
    lastcommand = None
    precision_string = '.' + str(PRECISION) + 'f'

    params = ['X', 'Y', 'Z', 'A', 'B', 'I', 'J', 'F', 'S', 'T', 'Q', 'R', 'L', 'P']  # This list control the order of parameters

    if hasattr(pathobj, "Group"):  # We have a compound or project.
        if OUTPUT_COMMENTS:
            out += linenumber() + "(compound: " + pathobj.Label + ")\n"
        for p in pathobj.Group:
            out += parse(p)
        return out

    else:  # parsing simple path

        if not hasattr(pathobj, "Path"):  # groups might contain non-path things like stock.
            return out

        if OUTPUT_COMMENTS:
            out += linenumber() + "(Path: " + pathobj.Label + ")\n"

        for c in pathobj.Path.Commands:
            outstring = []
            command = c.Name

            # Conversion des gCodes Charly différents du standard Unités
            if command == 'G21':
                command = 'G71'
            elif command == 'G20':
                command = 'G70'

            outstring.append(command)

            # Check for Tool Change:
            if command in ('M6', 'M06'):
                if OUTPUT_COMMENTS:
                    out += linenumber() + "(begin toolchange)\n"
                if not OUTPUT_TOOL_CHANGE:
                    outstring.insert(0, "(")
                    outstring.append(")")
                else:
                    for line in TOOL_CHANGE.splitlines(True):
                        out += linenumber() + line
                # Flag les changements d'outils pour assurer le mouvement suivant complet avec ses 3 coordonnées
                START_OR_M6 = True

            # if modal: only print the command if it is not the same as the last one
            if MODAL:
                if (command == lastcommand) and (command in MODAL_COMMANDS):
                    outstring.pop(0)

            # Now add the remaining parameters in order
            for param in params:
                if param in c.Parameters:
                    # Transforme les coordonnées IJK des interpolations circulaires en coordonnées absolues
                    if param == 'I':
                        pos = Units.Quantity(c.Parameters[param], FreeCAD.Units.Length) + CURRENT_X
                        outstring.append(param + format(float(pos.getValueAs(UNIT_FORMAT)), precision_string))
                    elif param == 'J':
                        pos = Units.Quantity(c.Parameters[param], FreeCAD.Units.Length) + CURRENT_Y
                        outstring.append(param + format(float(pos.getValueAs(UNIT_FORMAT)), precision_string))
                    elif param == 'F':
                        if command not in RAPID_MOVES:
                            # Conversion des unités (mm/s par defaut) de FreeCAD en mm/mn
                            speed = Units.Quantity(c.Parameters['F'], FreeCAD.Units.Velocity)
                            if speed.getValueAs(UNIT_SPEED_FORMAT) > 0.0:
                                outstring.append(param + format(float(speed.getValueAs(UNIT_SPEED_FORMAT)), precision_string))
                    elif param in ['T', 'H', 'D', 'S', 'P', 'L']:
                        outstring.append(param + str(c.Parameters[param]))
                    elif param in ['A', 'B', 'C']:
                        outstring.append(param + format(c.Parameters[param], precision_string))
                    else:  # [X, Y, Z, U, V, W, I, J, K, R, Q] (Conversion eventuelle mm/inches)
                        pos = Units.Quantity(c.Parameters[param], FreeCAD.Units.Length)
                        outstring.append(param + format(float(pos.getValueAs(UNIT_FORMAT)), precision_string))

            # store the latest command
            lastcommand = command

            if command in MOTION_COMMANDS:

                # Supprime les commandes de mouvement sans coordonnées de déplacement
                if len(list(c.Parameters.values())) == 0:
                    del(outstring[:])  # Efface la ligne inutile
                    outstring = []

                # Memorise la position courante pour toutes les commandes de mouvement
                # cette position sera utilisee pour recalculer les centres d'arcs G2, G3 en coordonnees absolues.
                # Utilisé aussi pour calcul des mouvements relatis et du plan de retrait des cycles de perçages.
                if 'X' in c.Parameters:
                    CURRENT_X = Units.Quantity(c.Parameters['X'], FreeCAD.Units.Length)
                if 'Y' in c.Parameters:
                    CURRENT_Y = Units.Quantity(c.Parameters['Y'], FreeCAD.Units.Length)
                if 'Z' in c.Parameters:
                    CURRENT_Z = Units.Quantity(c.Parameters['Z'], FreeCAD.Units.Length)

                # Force le premier deplacement ou le prochain déplacement après un changement d'outil à contenir les 3 axes X, Y et Z
                if START_OR_M6:
                    x_ok = False
                    y_ok = False
                    z_ok = False
                    for p in c.Parameters:
                        if p == 'X':
                            x_ok = True
                        if p == 'Y':
                            y_ok = True
                        if p == 'Z':
                            z_ok = True
                    if not x_ok:
                        outstring.insert(1, 'X{}'.format(format(float(CURRENT_X), precision_string)))
                    if not y_ok:
                        outstring.insert(2, 'Y{}'.format(format(float(CURRENT_Y), precision_string)))
                    if not z_ok:
                        outstring.insert(3, 'Z{}'.format(format(float(CURRENT_Z), precision_string)))
                    START_OR_M6 = False

            if command in ('G98', 'G99'):
                DRILL_RETRACT_MODE = command

            if command in ('G90', 'G91'):
                MOTION_MODE = command

            # Translation des cycles de perçages
            if command in ('G81', 'G82', 'G83'):
                out += drill_translate(outstring, command, c.Parameters)
                # Efface la ligne que l'on vient de translater
                del(outstring[:])
                outstring = []

            if command == "message":
                if OUTPUT_COMMENTS is False:
                    out = []
                else:
                    outstring.pop(0)  # remove the command

            if command in SUPPRESS_COMMANDS:
                outstring.insert(0, "(")
                outstring.append(")")

            # prepend a line number and append a newline
            if len(outstring) >= 1:
                out += linenumber() + format_outstring(outstring) + "\n"

        return out


def drill_translate(outstring, cmd, params):
    global DRILL_RETRACT_MODE
    global MOTION_MODE
    global CURRENT_X
    global CURRENT_Y
    global CURRENT_Z
    global UNITS
    global UNIT_FORMAT
    global UNIT_SPEED_FORMAT

    strFormat = '.' + str(PRECISION) + 'f'

    if OUTPUT_COMMENTS:  # Comment the original command
        trBuff = linenumber() + "(Translated {} drilling cycle to G0/G1 moves)\n".format(cmd)
        outstring.insert(0, "(")
        outstring.append(")")
        trBuff += linenumber() + format_outstring(outstring) + "\n"
    else:
        trBuff = ""

    # Conversion du cycle
    # On gere uniquement les cycles dans le plan XY (G17)
    # les autres plans ZX (G18) et YZ (G19) ne sont supportés par Charly robot
    # Calculs sur Z uniquement.

    if MOTION_MODE == 'G90':  # Deplacements en coordonnees absolues
        drill_X = Units.Quantity(params['X'], FreeCAD.Units.Length)
        drill_Y = Units.Quantity(params['Y'], FreeCAD.Units.Length)
        drill_Z = Units.Quantity(params['Z'], FreeCAD.Units.Length)
        RETRACT_Z = Units.Quantity(params['R'], FreeCAD.Units.Length)
    else:  # G91 Deplacements relatifs
        drill_X = CURRENT_X + Units.Quantity(params['X'], FreeCAD.Units.Length)
        drill_Y = CURRENT_Y + Units.Quantity(params['Y'], FreeCAD.Units.Length)
        drill_Z = CURRENT_Z + Units.Quantity(params['Z'], FreeCAD.Units.Length)
        RETRACT_Z = CURRENT_Z + Units.Quantity(params['R'], FreeCAD.Units.Length)

    if DRILL_RETRACT_MODE == 'G98' and CURRENT_Z >= RETRACT_Z:
        RETRACT_Z = CURRENT_Z

    # Recupere les valeurs des autres parametres
    drill_Speed = Units.Quantity(params['F'], FreeCAD.Units.Velocity)
    if cmd == 'G83':
        drill_Step = Units.Quantity(params['Q'], FreeCAD.Units.Length)
    elif cmd == 'G82':
        drill_DwellTime = params['P']

    if MOTION_MODE == 'G91':
        trBuff += linenumber() + "G90" + "\n"  # Force des deplacements en coordonnees absolues pendant les cycles

    # Mouvement(s) preliminaire(s))
    if CURRENT_Z < RETRACT_Z:
        trBuff += linenumber() + 'G0 Z' + format(float(RETRACT_Z.getValueAs(UNIT_FORMAT)), strFormat) + "\n"
    trBuff += linenumber() + 'G0 X' + format(float(drill_X.getValueAs(UNIT_FORMAT)), strFormat) + ' Y' + format(float(drill_Y.getValueAs(UNIT_FORMAT)), strFormat) + "\n"
    if CURRENT_Z > RETRACT_Z:
        trBuff += linenumber() + 'G0 Z' + format(float(CURRENT_Z.getValueAs(UNIT_FORMAT)), strFormat) + "\n"

    # Mouvement de percage
    if cmd in ('G81', 'G82'):
        trBuff += linenumber() + 'G1 Z' + format(float(drill_Z.getValueAs(UNIT_FORMAT)), strFormat) + ' F' + format(float(drill_Speed.getValueAs(UNIT_SPEED_FORMAT)), '.2f') + "\n"
        # Temporisation eventuelle
        if cmd == 'G82':
            trBuff += linenumber() + 'G4 P' + str(drill_DwellTime) + "\n"
        # Sortie de percage
        trBuff += linenumber() + 'G0 Z' + format(float(RETRACT_Z.getValueAs(UNIT_FORMAT)), strFormat) + "\n"
    else:  # 'G83'
        next_Stop_Z = RETRACT_Z - drill_Step
        while 1:
            if next_Stop_Z > drill_Z:
                trBuff += linenumber() + 'G1 Z' + format(float(next_Stop_Z.getValueAs(UNIT_FORMAT)), strFormat) + ' F' + format(float(drill_Speed.getValueAs(UNIT_SPEED_FORMAT)), '.2f') + "\n"
                trBuff += linenumber() + 'G0 Z' + format(float(RETRACT_Z.getValueAs(UNIT_FORMAT)), strFormat) + "\n"
                next_Stop_Z -= drill_Step
            else:
                trBuff += linenumber() + 'G1 Z' + format(float(drill_Z.getValueAs(UNIT_FORMAT)), strFormat) + ' F' + format(float(drill_Speed.getValueAs(UNIT_SPEED_FORMAT)), '.2f') + "\n"
                trBuff += linenumber() + 'G0 Z' + format(float(RETRACT_Z.getValueAs(UNIT_FORMAT)), strFormat) + "\n"
                break

    if MOTION_MODE == 'G91':
        trBuff += linenumber() + 'G91'  # Restore le mode de deplacement relatif

    return trBuff


print(__name__ + " gcode postprocessor loaded...")
