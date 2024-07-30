# King Arthur

King Arthur is the DevOps helper bot for Python Discord.

## A note on LDAP

By default, we install `bonsai`, which requires native modules to be installed
such as OpenLDAP.

> [!IMPORTANT]
> The LDAP cog will not load in development unless the
> `KING_ARTHUR_ENABLE_LDAP` environment variable is set
> to true, to avoid developers having to attempt to set
> up local emulations of the LDAP directory.

### Running on host
This section is not applicable if running in Docker.

Ensure you have the prerequisites for your host OS listed [here](https://bonsai.readthedocs.io/en/latest/install.html).

Once you have met these requirements, use the following to install all project
dependencies as well as the LDAP dependencies.

``` sh
$ poetry install --with ldap
```
