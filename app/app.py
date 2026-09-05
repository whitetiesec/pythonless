# Intentionally vulnerable demo application.
#
# Two RCE endpoints are exposed on purpose. They exist to demonstrate one point:
# removing the shell from a container (e.g. a distroless base image) does NOT
# remove the ability to run commands if the image still ships a capable
# interpreter such as Python.
#
#   POST /rce     -> shell-based RCE. Executes the decoded input via /bin/sh.
#                    On a distroless image (no /bin/sh) this FAILS with a 500.
#                    Demonstrates: distroless kills shell-dependent RCE and the
#                    whole class of "living off the land" binary post-ex.
#
#   POST /pyexec  -> interpreter-based RCE. exec()s the decoded input as Python,
#                    in-process, using zero external binaries and no shell.
#                    On the SAME distroless image this SUCCEEDS.
#                    Demonstrates: a shell-less container is not a
#                    code-execution-less container. The interpreter reimplements
#                    everything a shell would give you (os.getuid() for `id`,
#                    os.listdir() for `ls`, open().read() for `cat`, socket for
#                    a reverse shell, etc.).
#
# Both endpoints take the same request shape so the demo can send the identical
# payload to each and contrast the result:
#   form field `command` = base64-encoded payload
#
# DO NOT deploy this anywhere reachable. It is unauthenticated RCE by design.

from flask import Flask, request
import subprocess
import base64
import io
import contextlib

app = Flask(__name__)


@app.route('/rce', methods=['POST'])
def handle_command():
    # Shell sink: decoded bytes are handed to /bin/sh via shell=True.
    # Requires a shell to exist in the image. Fails on distroless.
    b64_input = request.form.get('command')
    command = base64.b64decode(b64_input)
    output = subprocess.check_output(command, shell=True)
    return output


@app.route('/pyexec', methods=['POST'])
def handle_pyexec():
    # Interpreter sink: decoded bytes are exec()'d as Python in-process.
    # No shell, no external binaries. Works on distroless because the
    # interpreter itself is the capability.
    # stdout produced by the injected code is captured and returned so the
    # command output shows up in the HTTP response, mirroring /rce.
    b64_input = request.form.get('command')
    code = base64.b64decode(b64_input)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(code, {})
    return buf.getvalue()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
