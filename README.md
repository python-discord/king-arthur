# King Arthur

King Arthur is the DevOps helper bot for Python Discord.

## Environment variables

### Core
These environment variables are required to start the bot

| Environment                           | Description                                                  | Required/Default          |
| ------------------------------------- | ------------------------------------------------------------ | ------------------------- |
| KING_ARTHUR_TOKEN                     | The bot token to authorize with Discord                      | Required                  |
| KING_ARTHUR_PREFIXES                  | The list of prefixes to listen to commands                   | `("arthur ", "M-x ")`     |
| KING_ARTHUR_DEVOPS_ROLE               | The Discord role that is allowed to run King Arthur commands | 409416496733880320        |
| KING_ARTHUR_GUILD_ID                  | The guild the bot should interact with                       | 267624335836053506        |
| KING_ARTHUR_DEVOPS_CHANNEL_ID         | The devops Discord channel                                   | 675756741417369640        |
| KING_ARTHUR_SENTRY_DSN                | Where to send sentry alerts                                  | ""                        |

### API integrations
These environment variables are required to work on the relevant cog.

| Environment                           | Relevant cog          | Description                                                               | Required/Default          |
| ------------------------------------- | --------------------- | ------------------------------------------------------------------------- | ------------------------- |
| KING_ARTHUR_CLOUDFLARE_TOKEN          | Zones                 | A token for the Cloudflare API used for the Cloudflare commands in Arthur | Required                  |
| KING_ARTHUR_GITHUB_ORG                | GrafanaGitHubTeamSync | The github organisation to fetch teams from                               | python-discord            |
| KING_ARTHUR_GITHUB_TOKEN              | GrafanaGitHubTeamSync | The github token used to fetch teams to populate grafana                  | Required                  |
| KING_ARTHUR_GRAFANA_URL               | GrafanaGitHubTeamSync | The URL to the grafana instance to manage teams                           | https://grafana.pydis.wtf |
| KING_ARTHUR_GRAFANA_TOKEN             | GrafanaGitHubTeamSync | The grafana token used to sync teams with github                          | Required                  |
| KING_ARTHUR_YOUTUBE_API_KEY           | Motivation            | The YouTube API key to fetch missions with                                | Required                  |

### LDAP & Directory integrations
The environment variables are required to work with the LDAP/FreeIPA system.

| Environment                           | Description                                                | Required/Default                                           |
| ------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------- |
| KING_ARTHUR_ENABLE_LDAP               | Whether the LDAP cog should be started                     | False                                                      |
| KING_ARTHUR_LDAP_BOOTSTRAP_CHANNEL_ID | Channel to send the LDAP account reset message             | 1266358923875586160                                        |
| KING_ARTHUR_LDAP_HOST                 | The FQDN of the host running LDAP                          | Required                                                   |
| KING_ARTHUR_LDAP_BIND_USER            | The LDAP user to use when making requests                  | uid=kingarthur,cn=users,cn=accounts,dc=box,dc=pydis,dc=wtf |
| KING_ARTHUR_LDAP_BIND_PASSWORD        | The password for the above user                            | Required                                                   |
| KING_ARTHUR_LDAP_BASE_DN              | The base distinguished name to use for requests to LDAP    | dc=box,dc=pydis,dc=wtf                                     |
| KING_ARTHUR_LDAP_CERTIFICATE_LOCATION | The location of the self signed cert to send with requests | Required                                                   |
| KING_ARTHUR_KEYCLOAK_ADDRESS          | The URL to the keycloak address to make requests to        | Required                                                   |
| KING_ARTHUR_KEYCLOAK_USERNAME         | The username of the keycloak user to make requests with    | kingarthur                                                 |
| KING_ARTHUR_KEYCLOAK_PASSWORD         | The password of the keycloak user to make requests with    | Required                                                   |
| KING_ARTHUR_KEYCLOAK_USER_REALM       | The keycloak realm to make requests to                     | pydis                                                      |
| KING_ARTHUR_EMAIL_HOST                | The e-mail relay to send e-mails via                       |                                                            |
| KING_ARTHUR_EMAIL_FROM                | The "From:" address to set in e-mails sent by King Arthur  |                                                            |
| KING_ARTHUR_EMAIL_USERNAME            | The username to authenticate to the mail relay with        |                                                            |
| KING_ARTHUR_EMAIL_PASSWORD            | The password to authenticate to the mail relay with        |                                                            |

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
