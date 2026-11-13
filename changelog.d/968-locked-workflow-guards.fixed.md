Release workflow checkouts no longer persist GitHub credentials during dependency
installation. Locked-install checks now detect ephemeral uv installs and require
the locked installer before Python steps, including third-party-only imports.
