# tiny-containers

CTFd admin plugin for global challenge Compose projects. It does not manage
per-team instances. The admin panel discovers Compose files under the configured
challenge repository; no challenge names or images are built into the plugin.
The CTFd challenge toggle controls which challenges appear in the Add search.
The Compose file choices come from the configured challenge repository. When
a challenge is selected, its name is converted to an underscore-separated
folder name to suggest a Compose file. If there is no clear match, the admin
searches for the file manually. No challenge names are embedded in the plugin.

Set these values in the CTFd Compose environment:

| Variable | Purpose |
| --- | --- |
| `TINY_CONTAINERS_REPO_PATH` | Absolute host path to the challenge repository. CTFd mounts it read-only at the same path so Docker Compose bind mounts resolve correctly. |
| `TINY_CONTAINERS_DOMAIN` | Base domain for challenge subdomains. |
| `TINY_CONTAINERS_DOCKER_SOCKET` | Docker socket path on the host. Defaults to `/var/run/docker.sock`. |
| `TINY_CONTAINERS_HTTP_PORT` | Host port for the plugin's Traefik listener. Defaults to `8080`; use `80` where the host allows it. |
| `TINY_CONTAINERS_HTTP_BIND` | Bind address for Traefik. Defaults to `0.0.0.0`. |
| `TINY_CONTAINERS_PROXY_NETWORK` | Docker network shared by Traefik and managed HTTP challenges. Defaults to `tiny-containers-proxy`. |

The first CTFd flag (ordered by flag ID) is provided to the project's services
as `FLAG` when it is launched. A challenge must use that variable for its running
flag; Compose files that embed flags in source or files need adapting before
being enabled. The CTFd connection information is set to the HTTP subdomain
when launch succeeds. Visibility in CTFd is independent of container runtime.

Building prepares every service in the Compose project without starting it.
Launch, restart, and stop also act on the whole project. The public service is
inferred from the project's single published TCP port, or from a single
`expose` port when none is published. Projects with multiple public ports need
one ingress port declared before they can be managed. That service receives
the Traefik route and published Port. TCP challenges use their subdomain and
published Port directly. Ports from the source Compose file are omitted in the
managed copy, and the source file is not edited. Compose does not identify
whether TCP traffic is HTTP, so the admin selects the access type. The Port
field defaults to the Compose published port. The admin pane shows health for
each service; the Logs view fetches recent logs for all services on demand.

The worker stops managed projects at the configured CTF end plus the grace
period (15 minutes by default). Without a CTF end time, it leaves them running.
