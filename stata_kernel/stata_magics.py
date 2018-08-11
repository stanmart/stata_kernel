import argparse
import regex
from .code_manager import CodeManager


# ---------------------------------------------------------------------
# Magic argument parsers


class MagicParsers():
    def __init__(self):
        self.plot = argparse.ArgumentParser()
        self.plot.add_argument(
            'code',
            nargs    = '*',
            type     = str,
            metavar  = 'CODE',
            help     = "Code to run")
        self.plot.add_argument(
            '--scale',
            dest     = 'scale',
            type     = float,
            metavar  = 'SCALE',
            default  = 1,
            help     = "Scale default height and width",
            required = False)
        self.plot.add_argument(
            '--width',
            dest     = 'width',
            type     = int,
            metavar  = 'WIDTH',
            default  = 600,
            help     = "Plot width",
            required = False)
        self.plot.add_argument(
            '--height',
            dest     = 'height',
            type     = int,
            metavar  = 'height',
            default  = 400,
            help     = "Plot height",
            required = False)
        self.plot.add_argument(
            '--set',
            dest     = 'set',
            action   = 'store_true',
            help     = "Permanently set plot width and height.",
            required = False)

        self.globals = argparse.ArgumentParser()
        self.globals.add_argument(
            'code',
            nargs    = '*',
            type     = str,
            metavar  = 'CODE',
            help     = "Code to run")
        self.globals.add_argument(
            '-t', '--truncate',
            dest     = 'truncate',
            action   = 'store_true',
            help     = "Truncate macro values to first line printed by Stata",
            required = False)


# ---------------------------------------------------------------------
# Hack-ish magic parser


class StataMagics():
    img_metadata = {
        'width': 600,
        'height': 400}

    magic_regex = regex.compile(
        r'\A%(?<magic>.+?)(?<code>\s+.*)?\Z',
        flags = regex.DOTALL + regex.MULTILINE
    )

    available_magics = [
        'plot',
        'graph',
        'exit',
        'restart',
        'locals',
        'globals',
        'time',
        'timeit'
    ]
    parse = MagicParsers()

    def __init__(self):
        self.quit_early = None
        self.status = 0
        self.any = False
        self.name = ''
        self.graphs = 1
        self.img_set = False

    def magic(self, code, kernel):
        self.__init__()

        if code.strip().startswith("%"):
            match = self.magic_regex.match(code.strip())
            if match:
                name, code = match.groupdict().values()
                code = '' if code is None else code.strip()
                if name in self.available_magics:
                    code = getattr(self, "magic_" + name)(code, kernel)
                    self.name = name
                    self.any = True
                    if code.strip() == '':
                        self.status = -1
                else:
                    print("Unknown magic %{0}.".format(name))
                    self.status = -1

                if (self.status == -1):
                    self.quit_early = {
                        'execution_count': kernel.execution_count,
                        'status': 'ok',
                        'payload': [],
                        'user_expressions': {}
                    }

        elif code.strip().startswith("?"):
            code = "help " + code.strip()

        return code

    def magic_graph(self, code, kernel):
        return self.magic_plot(code, kernel)

    def magic_plot(self, code, kernel):
        try:
            args = vars(self.parse.plot.parse_args(code.split(' ')))
            _code = ' '.join(args['code'])
            args.pop('code', None)
            args['width'] = args['scale'] * args['width']
            args['height'] = args['scale'] * args['height']
            args.pop('scale', None)
            self.img_set = args['set']
            args.pop('set', None)
            self.img_metadata = args
            self.graphs = 2
            return _code
        except:
            self.status = -1
            return code

    def magic_globals(self, code, kernel, local = False):
        gregex = {}
        gregex['blank'] = regex.compile(r"^ {16,16}", flags = regex.MULTILINE)
        try:
            args = vars(self.parse.globals.parse_args(code.split(' ')))
            code = ' '.join(args['code'])
            gregex['match'] = regex.compile(code.strip())
            if args['truncate']:
                gregex['main'] = regex.compile(
                    r"^(?<macro>_?[\w\d]*?):"
                    r"(?<cr>[\r\n]{0,2} {1,16})"
                    r"(?<contents>.*?$)",
                    flags = regex.DOTALL + regex.MULTILINE)
            else:
                gregex['main'] = regex.compile(
                    r"^(?<macro>_?[\w\d]*?):"
                    r"(?<cr>[\r\n]{0,2} {1,16})"
                    r"(?<contents>.*?$(?:[\r\n]{0,2} {16,16}.*?$)*)",
                    flags = regex.DOTALL + regex.MULTILINE)
        except:
            self.status = -1

        if self.status == -1:
            return code

        cm = CodeManager("macro dir")
        rc, imgs, res = kernel.stata.do(cm.get_chunks(), graphs = 0)
        stata_globals = gregex['main'].findall(res)

        lens = 0
        find_name = gregex['match'] != ''
        print_globals = []
        if len(stata_globals) > 0:
            for macro, cr, contents in stata_globals:
                if local and not macro.startswith('_'):
                    continue
                elif not local and macro.startswith('_'):
                    continue

                if macro.startswith('_'):
                    macro = macro[1:]
                    extra = 1
                else:
                    extra = 0

                if find_name:
                    if not gregex['match'].search(macro):
                        continue

                macro  += ':'
                lmacro  = len(macro)
                lspaces = len(cr.strip('\r\n'))
                lens    = max(lens, lmacro)
                if len(macro) <= 15:
                    if (lspaces + lmacro + extra) > 16:
                        print_globals += ((macro, ' ' + contents),)
                    else:
                        print_globals += ((macro, contents),)
                else:
                    print_globals += ((macro, contents.lstrip('\r\n')),)

        fmt = "{{0:{0}}} {{1}}".format(lens)
        for macro, contents in print_globals:
            print(fmt.format(
                macro, gregex['blank'].sub((lens + 1) * ' ', contents)))

        self.status = -1
        return ''

    def magic_locals(self, code, kernel):
        return self.magic_globals(code, kernel, True)

    def magic_time(self, code, kernel):
        self.status = -1
        print("Magic time has not yet been implemented.")
        return code

    def magic_timeit(self, code, kernel):
        self.status = -1
        print("Magic timeit has not yet been implemented.")
        return code

    def magic_exit(self, code, kernel):
        self.status = -1
        print("Magic restart has not yet been implemented.")
        return code

    def magic_restart(self, code, kernel):
        # magic['name']    = 'restart'
        # magic['restart'] = True
        # if code.strip() != '':
        #     magic['name']   = ''
        #     magic['status'] = -1
        #     print("Magic restart must be called by itself.")
        self.status = -1
        print("Magic restart has not yet been implemented.")
        return code
