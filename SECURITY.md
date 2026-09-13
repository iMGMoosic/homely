# Security

homely is meant to run on a home LAN. By default the web UI has **no authentication**:
anyone on your network can change what the display shows. Enable a password with
`sudo /opt/homely/venv/bin/homely config set-password` if that matters to you, and do not
expose port 8080 to the internet. Traffic is plain HTTP; put a reverse proxy with TLS in front
if you need it.

The service starts as root to initialise the LED matrix GPIO and immediately drops to the
unprivileged `homely` user. Reboot/shutdown from the UI use a sudoers entry limited to three
exact `systemctl` commands.

To report a vulnerability, open a private security advisory on GitHub or email the maintainer.
