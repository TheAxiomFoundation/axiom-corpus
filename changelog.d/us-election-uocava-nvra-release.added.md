Added the immutable `us-rulespec-2026-09-29-election-uocava-nvra` release selector,
the successor of `us-rulespec-2026-09-24-snap-fy2027-cola` that adds the Title 52
election statutes (52 U.S.C. 20302, 20310 and 20507) and, as the 2026-09-25
us-ca statute recovery audit requires of the next cut in this line, replaces the
California 2026-07-13 recovery and PIT core statute scopes with the 2026-09-14
income tax chapter scope. It is a publish-only pin release for rulespec-us: do
not dispatch it to `activate-release.yml`, because activation repoints every
serving pair it carries to this older lineage's scope versions and would
displace any newer release activated for those pairs.
