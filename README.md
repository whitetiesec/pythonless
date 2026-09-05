# pythonless — intentionally vulnerable RCE demo

A minimal Flask app used **only for security demonstrations**. It exposes two
unauthenticated remote-code-execution endpoints on purpose. Together they make
one point:

> Removing the shell from a container (for example by using a distroless base
> image) does **not** remove the ability to run commands if the image still
> ships a capable interpreter such as Python. A shell-less container is not a
> code-execution-less container.

> ⚠️ **Do not deploy this anywhere reachable.** It is unauthenticated RCE by
> design. Run it locally, on an isolated network, for demos only.

## The two endpoints

Both take the same request shape so you can send the identical payload to each
and contrast the result:

- Method: `POST`
- Form field: `command` = **base64-encoded** payload

| Endpoint  | Sink                                   | Needs a shell? | On distroless |
|-----------|----------------------------------------|----------------|---------------|
| `/rce`    | `subprocess.check_output(cmd, shell=True)` | Yes (`/bin/sh`) | **Fails (500)** |
| `/pyexec` | `exec(code)` in-process                | No             | **Succeeds**  |

- **`/rce`** is the classic shell RCE. The decoded input is run through
  `/bin/sh`. On a distroless image there is no `/bin/sh`, so every request
  raises `FileNotFoundError` and returns HTTP 500. This shows distroless doing
  its job: it kills shell-dependent RCE and the whole class of "living off the
  land" binary post-exploitation (`id`, `ls`, `cat`, `nc`, ...).

- **`/pyexec`** is the interpreter RCE. The decoded input is `exec()`'d as
  Python, in-process, using zero external binaries and no shell. On the *same*
  distroless image it succeeds, because the interpreter itself is the
  capability. stdout from the injected code is captured and returned in the
  response, mirroring `/rce`.

The interpreter reimplements everything the shell would have given you:

| Shell command | Pure-Python equivalent (works on distroless) |
|---------------|----------------------------------------------|
| `id`          | `os.getuid()`, `os.getgid()`                 |
| `ls /`        | `os.listdir('/')`                            |
| `cat FILE`    | `open('FILE').read()`                         |
| reverse shell | `socket` + `exec` (see `app/payload`)         |

## Project structure

```
.
├── compose.yaml
├── app
│   ├── Dockerfile        # distroless final image (no shell) — the "hard" target
│   ├── Dockerfile.back   # alpine variant (HAS a shell) — use to demo /rce succeeding
│   ├── requirements.txt
│   ├── app.py            # both endpoints
│   └── payload           # pure-Python staged reverse shell (socket + exec)
```

## Run it

```bash
docker compose up -d --build
docker compose ps        # web running, 0.0.0.0:8000->8000/tcp
```

By default `compose.yaml` builds `app/Dockerfile` (distroless). To demo `/rce`
succeeding as well, build the shell-bearing alpine variant instead — either
point `compose.yaml`'s `build` at `Dockerfile.back`, or:

```bash
cd app && mv Dockerfile Dockerfile.distroless && mv Dockerfile.back Dockerfile
```

## Reach it with a successful request

`/pyexec` (works on distroless — no shell in the container):

```bash
# id / ls equivalents, pure Python
curl -s -X POST http://localhost:8000/pyexec \
  --data-urlencode "command=$(printf 'import os
print("uid=%d gid=%d" % (os.getuid(), os.getgid()))
print(os.listdir("/")[:5])' | base64)"

# cat equivalent
curl -s -X POST http://localhost:8000/pyexec \
  -d "command=$(printf 'print(open("/etc/hostname").read().strip())' | base64)"
```

`/rce` (works only when the image has a shell, e.g. the alpine build):

```bash
curl -s -X POST http://localhost:8000/rce \
  -d "command=$(printf 'id; uname -a' | base64)"
```

On the distroless build, the `/rce` call above returns HTTP 500 (no `/bin/sh`)
while the `/pyexec` calls still return output. That contrast is the demo.

## Reverse shell (optional, the payload file)

`app/payload` is a pure-Python staged reverse shell. It uses only stdlib
(`socket`, `zlib`, `base64`, `struct`, `exec`), so it runs on distroless with no
shell and no external tools. It connects back to `172.17.0.2:4444`; edit that
address to match wherever your listener/handler runs. Deliver it by base64-ing
its contents into `/pyexec`.

## Tear down

```bash
docker compose down
```
