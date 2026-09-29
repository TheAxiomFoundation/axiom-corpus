Added the immutable `us-rulespec-2026-09-29-election-uocava-nvra` release selector,
preserving the scopes of `us-rulespec-2026-09-24-snap-fy2027-cola` and adding the
Title 52 election statutes (52 U.S.C. 20302, 20310 and 20507). It is a
publish-only pin release for rulespec-us: do not dispatch it to
`activate-release.yml`, because activation repoints every serving pair it carries
to this older lineage's scope versions and would displace any newer release
activated for those pairs.
