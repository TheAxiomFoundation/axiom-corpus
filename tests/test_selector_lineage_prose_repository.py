"""Recorded prose bases preserve selector lineage and their reviewed evidence (#970).

These expectations were captured from the tracked descriptions on 2026-11-05.
Full description hashes matter because selector_sha256 deliberately omits prose.
This file reads tracked manifests only, so partial corpus checkouts are sufficient.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import pytest

from axiom_corpus.corpus.releases import ReleaseManifest
from axiom_corpus.corpus.selector_lineage import (
    LineageBaseline,
    check_selector_lineage,
    load_tracked_selectors,
)
from axiom_corpus.release.manifest import selector_sha256

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RECORDED_ON = "2026-11-05"

# Reviewed selector, the one its prose identifies, and the exact description words.
_EVIDENCE_EDGES = (
    (
        "bo-rulespec-2026-07-24",
        "bo-rulespec-2026-07-23",
        "the BOLMOD t1 scopes plus",
    ),
    (
        "bo-rulespec-2026-07-24-r2",
        "bo-rulespec-2026-07-24",
        "the BOLMOD t1 scopes, the Ley 065 t2 slices, and",
    ),
    (
        "co-rulespec-2026-07-24",
        "co-rulespec-2026-07-23",
        "the COLMOD t1 scopes plus",
    ),
    (
        "de-rulespec-2026-07-21",
        "de-rulespec-2026-07-16",
        "Composes the byte-identical 2026-07-16 gesetze-im-internet consolidations with",
    ),
    (
        "de-rulespec-2026-09-08-kindergeld-2025-history",
        "de-rulespec-2026-09-08-kindergeld-context",
        "Preserves all twenty context-release scopes",
    ),
    (
        "de-rulespec-2026-09-08-kindergeld-civil",
        "de-rulespec-2026-09-08-kindergeld-frontier",
        "Preserves all fourteen published September frontier scopes",
    ),
    (
        "de-rulespec-2026-09-08-kindergeld-context",
        "de-rulespec-2026-09-08-kindergeld-civil",
        "Preserves all seventeen civil-release scopes",
    ),
    (
        "de-rulespec-2026-09-08-kindergeld-parentage",
        "de-rulespec-2026-09-08-kindergeld-civil",
        "Preserves all seventeen civil-release scopes",
    ),
    (
        "de-rulespec-2026-09-09-kindergeld-allowance-context",
        "de-rulespec-2026-09-08-kindergeld-2025-history",
        "Retains all 22 earlier scopes",
    ),
    (
        "de-rulespec-2026-09-09-kindergeld-bgb-amendment",
        "de-rulespec-2026-09-09-kindergeld-estg32-paragraphs",
        "Retain all30preceding scopes",
    ),
    (
        "de-rulespec-2026-09-09-kindergeld-bmf-context",
        "de-rulespec-2026-09-09-kindergeld-allowance-context",
        "Preserves all23preceding scopes",
    ),
    (
        "de-rulespec-2026-09-09-kindergeld-estg32-paragraphs",
        "de-rulespec-2026-09-09-kindergeld-eu-articles",
        "Preserve all29prior scopes",
    ),
    (
        "de-rulespec-2026-09-09-kindergeld-eu-articles",
        "de-rulespec-2026-09-09-kindergeld-swiss-coordination",
        "Preserves all28prior scopes",
    ),
    (
        "de-rulespec-2026-09-09-kindergeld-marginal-employment",
        "de-rulespec-2026-09-09-kindergeld-dakg",
        "Preserve all 37 preceding DE scopes",
    ),
    (
        "de-rulespec-2026-09-09-kindergeld-swiss-coordination",
        "de-rulespec-2026-09-09-kindergeld-treaty-texts",
        "Preserves all27prior scopes",
    ),
    (
        "de-rulespec-2026-09-09-kindergeld-threshold",
        "de-rulespec-2026-09-09-kindergeld-marginal-employment",
        "Preserve all 40 preceding DE scopes",
    ),
    (
        "de-rulespec-2026-09-09-kindergeld-treaty-texts",
        "de-rulespec-2026-09-09-kindergeld-bmf-context",
        "Preserves all24prior scopes",
    ),
    (
        "de-rulespec-2026-09-10-kindergeld-eu-service-earlier",
        "de-rulespec-2026-09-10-kindergeld-eu-service-predecessors",
        "Preserve all47 preceding DE scopes",
    ),
    (
        "de-rulespec-2026-09-10-kindergeld-eu-service-predecessors",
        "de-rulespec-2026-09-10-kindergeld-recipient-priority",
        "Preserve all46 preceding DE scopes",
    ),
    (
        "de-rulespec-2026-09-10-kindergeld-generations-service",
        "de-rulespec-2026-09-10-kindergeld-eu-service-earlier",
        "Preserve48prior DE scopes",
    ),
    (
        "de-rulespec-2026-09-10-kindergeld-maternity",
        "de-rulespec-2026-09-09-kindergeld-threshold",
        "Preserve all 41 preceding DE scopes",
    ),
    (
        "de-rulespec-2026-09-10-kindergeld-recipient-priority",
        "de-rulespec-2026-09-10-kindergeld-maternity",
        "Preserve all45 preceding DE scopes",
    ),
    (
        "de-rulespec-2026-09-11-kindergeld-bgh-counterpart",
        "de-rulespec-2026-09-11-kindergeld-disability-definition",
        "Preserve all52 preceding release scopes",
    ),
    (
        "de-rulespec-2026-09-11-kindergeld-bgh-form-predecessor",
        "de-rulespec-2026-09-11-kindergeld-bgh-counterpart",
        "Preserve all54 preceding DE scopes",
    ),
    (
        "de-rulespec-2026-09-11-kindergeld-disability-definition",
        "de-rulespec-2026-09-11-kindergeld-illness-precedents",
        "Preserve all50 prior DE scopes",
    ),
    (
        "de-rulespec-2026-09-11-kindergeld-illness-precedents",
        "de-rulespec-2026-09-10-kindergeld-generations-service",
        "Preserve all 49 prior DE scopes",
    ),
    (
        "de-rulespec-2026-09-14-kindergeld-dakg2025-evidence",
        "de-rulespec-2026-09-14-kindergeld-eu-territory",
        "Preserve all 56 prior DE scopes",
    ),
    (
        "de-rulespec-2026-09-14-kindergeld-dakg2025-sections",
        "de-rulespec-2026-09-14-kindergeld-dakg2025-evidence",
        "Preserve all 57 prior DE scopes",
    ),
    (
        "de-rulespec-2026-09-14-kindergeld-eu-territory",
        "de-rulespec-2026-09-11-kindergeld-bgh-form-predecessor",
        "Preserve all 55 preceding DE scopes",
    ),
    (
        "de-rulespec-2026-09-15-kindergeld-cross-border-priority",
        "de-rulespec-2026-09-15-kindergeld-dakg2025-preface",
        "Preserve all 59 prior DE scopes",
    ),
    (
        "de-rulespec-2026-09-15-kindergeld-dakg2025-preface",
        "de-rulespec-2026-09-14-kindergeld-dakg2025-sections",
        "Preserve all58 prior DE scopes",
    ),
    (
        "dk-rulespec-2026-08-22",
        "dk-rulespec-2026-08-07",
        "the 2026-08-07 Tier-1 full-parity statute scope",
    ),
    (
        "ec-rulespec-2026-07-24",
        "ec-rulespec-2026-07-22",
        "the ECUAMOD t1 scopes plus",
    ),
    (
        "nz-rulespec-2026-07-19",
        "nz-rulespec-2026-07-18",
        "the 2026-06-16 PCO statute and regulation scopes and the 2026-07-18 Wellington district-plan scope carried unchanged",
    ),
    (
        "nz-rulespec-2026-07-20",
        "nz-rulespec-2026-07-19",
        "the 2026-06-16 PCO statute and regulation scopes, the 2026-07-18 Wellington district-plan scope, and the 2026-07-19 PCO supplement scopes carried unchanged",
    ),
    (
        "nz-rulespec-2026-07-25",
        "nz-rulespec-2026-07-20",
        "the 2026-06-16 PCO statute and regulation scopes, the 2026-07-18 Wellington district-plan scope, the 2026-07-19 PCO supplement scopes, and the 2026-07-20 guidance scope carried unchanged",
    ),
    (
        "pe-rulespec-2026-07-24",
        "pe-rulespec-2026-07-22",
        "the PERUMOD t1 scopes plus",
    ),
    (
        "uk-rulespec-2026-08-08",
        "uk-rulespec-2026-08-07",
        "2026-08-07 set plus",
    ),
    (
        "uk-rulespec-2026-08-10",
        "uk-rulespec-2026-08-08",
        "2026-08-08 set plus",
    ),
    (
        "uk-rulespec-2026-09-05",
        "uk-rulespec-2026-08-10",
        "2026-08-10 set plus",
    ),
    (
        "uk-rulespec-2026-09-06",
        "uk-rulespec-2026-09-05",
        "2026-09-05 set plus",
    ),
    (
        "uk-rulespec-2026-09-07",
        "uk-rulespec-2026-09-06",
        "2026-09-06 set plus",
    ),
    (
        "us-rulespec-2026-07-16",
        "us-rulespec-2026-07-13",
        "Re-cut of the 07-13 plan",
    ),
    (
        "us-rulespec-2026-07-19",
        "us-rulespec-2026-07-18",
        "all other July 18 scope selections remain unchanged",
    ),
    (
        "us-rulespec-2026-07-19-dedup",
        "us-rulespec-2026-07-19",
        "all other July 19 scope selections",
    ),
    (
        "us-rulespec-foundation-v4-2026-07-15",
        "us-rulespec-foundation-v3-2026-07-15",
        "adding the CMS Medicaid/CHIP/BHP eligibility table to the v3 foundation",
    ),
    (
        "us-rulespec-foundation-v5-2026-07-15",
        "us-rulespec-foundation-v4-2026-07-15",
        "adding the CHIP Title XXI legal hierarchy to the v4 foundation",
    ),
    (
        "us-rulespec-snap-2026-07-21",
        "us-rulespec-2026-07-19-dedup",
        "Successor to the collision-free RuleSpec US release",
    ),
    (
        "vn-rulespec-2026-07-24-r2",
        "vn-rulespec-2026-07-24",
        "the VNMOD t1 scopes plus",
    ),
)

# Pair-scoped derivations identify a source for only part of its serving pairs.
# They remain first cuts rather than advancing that source's whole line.
_PAIR_SCOPED_DERIVATIONS = (
    (
        "us-az-snap-ece-2026-10-23-manual-union",
        "us-rulespec-2026-10-13-w7-bundle-gaps-union",
        (
            "Preserves every Arizona manual scope in the active W7 union",
            "Other serving jurisdiction/document-class pairs are deliberately unchanged.",
        ),
    ),
)

# Full description SHA256, then selector_sha256, captured before implementation.
_EVIDENCE_DIGESTS = {
    "bo-rulespec-2026-07-23": (
        "c83af023f22fa65f22f05c16c9bcd49c2eb3d0d48b1e959a49889620e711360f",
        "9e16dcfdf3ca5acb3235d419392cebabdc6da0edd100e75b7f5051747dc479fd",
    ),
    "bo-rulespec-2026-07-24": (
        "1099bce529a1a22bc32eafd3fcd5c29351a299b916459aa77311c5c1e0721cc0",
        "faa41653f6447b12776e021193152bae19b2d659b0452b09d8428341410d3a44",
    ),
    "bo-rulespec-2026-07-24-r2": (
        "078a33182f308e6347291a263170d8f30354fc5c9a1a816e258e2672fda3a643",
        "0aabe666da3351b8325629313a122909d8191001fd222dd6a203e2a3ee494541",
    ),
    "co-rulespec-2026-07-23": (
        "c39731f97f810f558cfad9555e754b0b904b0bc95212991d4afef9c9eef830c9",
        "530a3c64a3c7b35703979d037e6128f6a616eb02a595d888fff8ca90f216c120",
    ),
    "co-rulespec-2026-07-24": (
        "c5a0e0b7d41f954a9959fa9f70673988586fbf3e52ff49aca7e8ca4123633ecb",
        "30243f217800b967bdf964cbc89d3267d7e5777daabd9ff69ddb000c62a5a645",
    ),
    "de-rulespec-2026-07-16": (
        "cb3a3d55cedf101353fb7763d86098f0db5b1a43413f7b31308a709e4c483b36",
        "95ab4f21767cfd7435a423e885ad87cc4ca4c39b2a08f981c01a210ca9c00f3b",
    ),
    "de-rulespec-2026-07-21": (
        "9eee6b4bd1d28ef3ff5092ee400588c4c2e264efc716e4772f5d0717dd58c2a3",
        "106612aa6075a23fae4aae7fc80c39920cb6e0ff95e38694baa6191f8f3905f5",
    ),
    "de-rulespec-2026-09-08-kindergeld-2025-history": (
        "2fef824911e11ee298341c2ee6ea22d0148b2fbcc497e0cf378c594d047e9485",
        "379332d080b513de848338be2495f29370d6280e487791228d12a4efc15687e0",
    ),
    "de-rulespec-2026-09-08-kindergeld-civil": (
        "38a43d71a42ae3aca3c73e8515d5507dcbd2075a175f5cd9a9396aa956e8798f",
        "76600c66ac8b9b6c5740ca8fb300a975b717879f6751a4f6d2e061ce84258940",
    ),
    "de-rulespec-2026-09-08-kindergeld-context": (
        "0b0fcda11b3b35eb00285cf8c585aa2d37b975d028d9132836f7b9b7b7cc4412",
        "3f3392ce27bf299c991ef6305017a0491f550552bbd3e5e9fdd859519dca6b68",
    ),
    "de-rulespec-2026-09-08-kindergeld-frontier": (
        "c0b5c7e370c8b77a99f1e04518d214793e3065e2f5803151150ab31df8b0c63a",
        "9d5fd12e8110bfa1cad19cf46645989941da3457e1c998c8db7e251440939404",
    ),
    "de-rulespec-2026-09-08-kindergeld-parentage": (
        "0b0fcda11b3b35eb00285cf8c585aa2d37b975d028d9132836f7b9b7b7cc4412",
        "9aae8581d66731d1a72ae70784a59bd8b9503c3f4be901b1949321f35a3de95f",
    ),
    "de-rulespec-2026-09-09-kindergeld-allowance-context": (
        "aeaa6af8fbc3eec8e37ab57e5fea33515989a0b9bbc997c220d43347b5d3e4ff",
        "064b0c353046849d896c4d36c56c63620ca54921ad5f6c00bcfc4aee7889ce78",
    ),
    "de-rulespec-2026-09-09-kindergeld-bgb-amendment": (
        "478c59f70164eaa7c960c5af86d828a07b721f6a32827340ef57096496c63622",
        "5d6b446eca6d292b3c24ba36d280e58ed1d4ec631a6f7094e70145ef213b3647",
    ),
    "de-rulespec-2026-09-09-kindergeld-bmf-context": (
        "d2defc33097b9e7d3cf65e8f43078ec2d08b6978df0c620401d1f2b8c7c128d2",
        "f45b1dc24d2187706b6e0680819deabbe76182580dbcd4785f53dc6707f8b95f",
    ),
    "de-rulespec-2026-09-09-kindergeld-dakg": (
        "45f2073754cb5923acb3c15dea11c4637f96738550ba85bec6437a35d10894e1",
        "c09e67bd0c245bc5ab121f192cea129246c2cb129ec12ea945a6cc269482e62a",
    ),
    "de-rulespec-2026-09-09-kindergeld-estg32-paragraphs": (
        "06609524f1490a378190fcd982300269486138f64bdc567e3d35f2284ac661dd",
        "713a7514188325379fd58218c828912402e60b26271f5a29702089684ad89aa7",
    ),
    "de-rulespec-2026-09-09-kindergeld-eu-articles": (
        "5abd58dc043f56868312105fba2f2e4a360f25871007c5c69afd7890e5811a16",
        "827056319929968ac40a34d43f24b18652e5d991c35226a1b6b42d97d2386409",
    ),
    "de-rulespec-2026-09-09-kindergeld-marginal-employment": (
        "90bf4b4e7015d86da16448dfc00441664b39f427950c977240cc794a2f52f0fe",
        "27a7a2058e3f56c57fa9c7e1a92bc08dc29d2b2c0a8e9e1cbba75f0549771074",
    ),
    "de-rulespec-2026-09-09-kindergeld-swiss-coordination": (
        "d8acf0020469803025160da17629e60f2fd57b1dc33ea8e9ca00ffa45bfb5843",
        "fff38c38e07dce53e492e754a8812069641643b0e4ff3e47f03d5a54a0203721",
    ),
    "de-rulespec-2026-09-09-kindergeld-threshold": (
        "5887f8bd4268caa3ecf9fa3882286280df5b9262364fed8f9c16127a8944f2ec",
        "751e5c7e7aa9cb97dbe1f38b4dca183f3482fd6f24cdf3fcf97587aa6c341212",
    ),
    "de-rulespec-2026-09-09-kindergeld-treaty-texts": (
        "e7f8115af2a9b3f03581a17cfde1ccaf235831f00045e480abbda5f36ea69e35",
        "57f442572d728f35d821b9f8e4a994a0410040baeeb43e29287cd9190a3e0996",
    ),
    "de-rulespec-2026-09-10-kindergeld-eu-service-earlier": (
        "ad83d2736e2320606d49d4ea94d1d4b2cf69d149758e9a828723c81525111d7d",
        "ab820cd80aad283252b606ac7dc10e075bb286d69163666d2a63635077494732",
    ),
    "de-rulespec-2026-09-10-kindergeld-eu-service-predecessors": (
        "3e2c4a9606c255f78ad96dd8f7f3bc2745b1419fa769cbcdf97c71eae943f613",
        "2bba8f8afc9b6a179bac132a9721268515b696bba7a093befde58ad030142689",
    ),
    "de-rulespec-2026-09-10-kindergeld-generations-service": (
        "1a43a61a0b82464cfb87b55a69aabb32670fbdf17f7f704e742b3e244b3e79eb",
        "5d048faacf21ec2df0934a56b9af629787810fd44cda37044258fb37d9d84f71",
    ),
    "de-rulespec-2026-09-10-kindergeld-maternity": (
        "413f55c1261f616fd50afad9a014731adb4c629fccc05016f383b633946acaa0",
        "46b58c751d3defeffdaef986ddb39443e5de45d292881e76ad4c7b38c89ab0c2",
    ),
    "de-rulespec-2026-09-10-kindergeld-recipient-priority": (
        "30dfb205470fe2ff6d19517d643eccc68a17415fb090d3de33070f2e8a234a82",
        "334b1e1edb7826341da11a4069f801e4dedab795734aae1607aa38e338dbbe9b",
    ),
    "de-rulespec-2026-09-11-kindergeld-bgh-counterpart": (
        "d0c121c7a99ec1dec301caae4f0e715a30d69407325ee86156d0e6adc4095bc6",
        "6f52b6c60dc8898e1c36de6e6dc3c2fa1cd4c012a87fe4fb4a9994e8b314c3ac",
    ),
    "de-rulespec-2026-09-11-kindergeld-bgh-form-predecessor": (
        "c976123ebdc130440c4ef3edcd8ae0a4970caae6f2db4d924d1432b298ab2830",
        "440bc1611dd3d2cde8e82fd3cee430180d216d7947d5d80c67bdedca6cf34c5b",
    ),
    "de-rulespec-2026-09-11-kindergeld-disability-definition": (
        "2d3e75f29c50b72cb97aa4084c0883f7208ab81fc7c33a304f6dcd269bb05c1d",
        "dd95c1280fa612344b731ef72493b25c53b08c506d3d3499e697a6dfa7b89729",
    ),
    "de-rulespec-2026-09-11-kindergeld-illness-precedents": (
        "c0d7df19d9a1fe1e88711bef8c19dc23212cb5ddf75ab9c69f525eb118d0d181",
        "a8f4521f60195362fa2aec2034a44aa4777775572a4a13bc906332090d4ba945",
    ),
    "de-rulespec-2026-09-14-kindergeld-dakg2025-evidence": (
        "ee6dcf3283bf02a323e64a39e6b3236bd65dee4b09496a49b151d605f6837a05",
        "f8df4bb02786b5123b06adcbd7ab5b6e62299216f67493394a557fcd60301c74",
    ),
    "de-rulespec-2026-09-14-kindergeld-dakg2025-sections": (
        "d3ba6954ae54bb9695554f69f37b6807e18e0488995dafba1fac4c32f74639bd",
        "3b4f1f9fc163a1ab6e80d9e46f4a286ca406660c34e05339f4557d42454e0f05",
    ),
    "de-rulespec-2026-09-14-kindergeld-eu-territory": (
        "2c6070d68cdbf17cd95c29dc87693055bfb606c54cf0926e01f55be374b7882d",
        "309eb77793c927637b5f482036d47fb5267e3f47013b3f3fd371bd48a254adc8",
    ),
    "de-rulespec-2026-09-15-kindergeld-cross-border-priority": (
        "738f2b8f74a4ab1e782ad169f0e6c21daff0133808b2a38fd2f1e2cad354fac5",
        "f06d72f9b19d4a76f8d7cfe7a8492272262d5eab3cd70ec97f0967588cd4408d",
    ),
    "de-rulespec-2026-09-15-kindergeld-dakg2025-preface": (
        "62fcd72c61b6b0251e8144975fdfe454a26c89a341f7c58ac9e7735cb5246d10",
        "dce4dbdd45da7d287888e7a438d417e9873187320f659dc8f58ea806c143c732",
    ),
    "dk-rulespec-2026-08-07": (
        "d6a08e59b8538774b8210f2b47c00b0301686e345845a3c176c22a5483eae566",
        "0d9e3e02d05e0d36b45a16545ebe80b2f26f990ec1064a2d17a75831d4b6bb3d",
    ),
    "dk-rulespec-2026-08-22": (
        "60066d2f1c64b8d0de4b3159af5c64bb1232101cfd63c80570cc7947b4cce618",
        "ff4b159d7570d17bc714db49181678074156fec211aa4bb2180b97d8ca7f5ebb",
    ),
    "ec-rulespec-2026-07-22": (
        "e940ac10139a2bf5524f361941ea0fff2eb999ad298664d3a0458f732fd9d7ba",
        "bf00211838d253e081ba1c14361d6655fa930bc60c83153b93404a7d32ce28e5",
    ),
    "ec-rulespec-2026-07-24": (
        "19bf71554dd351080594bdb45d6d23166fbcfe88ac6a9dbd888b363e080acdd8",
        "aebf79c37248f0f9930bfe9500a19642abea35f43412b04b39b0b766a169d170",
    ),
    "nz-rulespec-2026-07-18": (
        "efd66d8affb2d60bd31cd1fb2a354a27dee3d8681d0e8aa389cc00f85b0fb819",
        "12c5f596b0203d6c4b7350aad46ba63e89151cc89f9b3c69db1e366b47163e93",
    ),
    "nz-rulespec-2026-07-19": (
        "bebfeb7a78189895de29a0bfdeea595d6a8878943e8069dec102e104caf500cc",
        "dee7557919863fc95fcbd93792fd1f246b9e7bd68cddb35681a71b603820699b",
    ),
    "nz-rulespec-2026-07-20": (
        "4ffa39b38e93e5d1b064ffefe2e2081b97d70831ea82b720a8b7b43a5b78c834",
        "03558a39482d62c876c2189656f69346f2c5bb28b0d99298084f6c03b1783ce7",
    ),
    "nz-rulespec-2026-07-25": (
        "4e0d30260aff1980bfc81d328adac2dfe0cc80f6da27696efcfb055551363215",
        "642ce790c1b38cf9224df8450e45340a02e7d5e00c28fcb12dc947f2afa08b43",
    ),
    "pe-rulespec-2026-07-22": (
        "2752f8e8e70ec14b9217782d294b64d6bb07d6c228c3909ad3464a1dea181966",
        "93b00b211a313a3e199aa018406c651c0795593526e0094aa5a8e464a288d105",
    ),
    "pe-rulespec-2026-07-24": (
        "eb478856f4a68d65e75cb58bf1ea8ad24165ca15b3191d630d1c881ff843a246",
        "2e26ec6702ab8dd63c7ab07399335582444f616886d2bdb4533815c1d734a462",
    ),
    "uk-rulespec-2026-08-07": (
        "1a0f99e126095908b78d33f8f1ce971f5de8b039bb360137a693c3423a1ce3d5",
        "2a9fe63b01bac2179a78088e40dca5c05ba676de714262fae0f2f44c6902ed43",
    ),
    "uk-rulespec-2026-08-08": (
        "aa2385856557e0ba6118015cf728979478c9eedc05560f912f7d11a59d79d3aa",
        "3c859df5a746290b7d945e79b41cf7e2a1db1893d1d1b3d5dbfa8f84ce57cf5e",
    ),
    "uk-rulespec-2026-08-10": (
        "698a55baffe0bf52e36955a4985803e1303d1c07b14162099dc6c074c9499b81",
        "2f33cfee351b9e165b30e65e08dd77151ad7d1507ca606fa25a3b634c44f1ec9",
    ),
    "uk-rulespec-2026-09-05": (
        "87b95872a9781173bce848e622de07b5c535917032f99dae912352009eaf2d3f",
        "827ed5d5a005734d5145583ffaa8fef5fbdd1fb85d874d2a274e4382f99c066d",
    ),
    "uk-rulespec-2026-09-06": (
        "952e2314564e8e71666d8b934b57f1f3c8800116d7c9bad9931f90619c10adb5",
        "1f1ded6be3d2d5243f0633bb3f211a35cf70c6e73f961891492aa70cf4f4f6bd",
    ),
    "uk-rulespec-2026-09-07": (
        "b8a33231fbd28a438793a42a2824cba66d2bd2bec81162dd8206f01ef63184a6",
        "3b25db3ea0fe1ee6c2576f7776b86aeb2da45b473c950c0639288a70ae92c71f",
    ),
    "us-rulespec-2026-07-13": (
        "2cb75891a3413407a7fd94f3f3bbe2c8fde0cec0dcea02306950967556394375",
        "6c98bfd3939049d1231112f1ea91c0825cd1ef4d43d19bf31eadfce2a049507a",
    ),
    "us-rulespec-2026-07-16": (
        "90ed6501acaf91a6b757dc359c44ef1df67717d607588d6dfc462d1d10aa4a28",
        "9c7654f832aa4ee584b3c1f6b1a8a89b87e7a441a2d8ebc3e2d61e4881e12bcf",
    ),
    "us-rulespec-2026-07-18": (
        "13d3ef6a997f7bc59ee85fa8e53a49ad38d78aef57280d204202d204b9234f32",
        "8e3919eacc86fe4c092f6a1a5d1c5d35cacd3bac461337590a63372c2e789311",
    ),
    "us-rulespec-2026-07-19": (
        "7d4f06f51056056d9c66d1a61145d43eb7535fade919938eb5b9f760fbe1f5d4",
        "79c091b4501eecb2996936ba51c87955f89460d9e3690b0fde88c30742547e9d",
    ),
    "us-rulespec-2026-07-19-dedup": (
        "6288582fc23cc952ec52a53b2e8369f36d9a6e5c3d8048e6fcd5175d7609affa",
        "6b18a3e3842b5cfa0736fc0352fada4d07d2417912383e0847b84a1e121552d6",
    ),
    "us-rulespec-foundation-v3-2026-07-15": (
        "b6b54abb5ee6bc1aae9ea2dc699ffb2af038769a3208a89081f6bb4ad966171e",
        "e611ad5be69a3247ea546d1b66f815492f0f83e58f820f1d4af64baf5f716fc7",
    ),
    "us-rulespec-foundation-v4-2026-07-15": (
        "f4d1a6bb904402f1082a3a820000c97c70ce1eece438f7233c5005afbffd25a5",
        "a2ad8ffb1bee801aa8c157fbff64de3f068cad459f65bef8d0edee7983394bc5",
    ),
    "us-rulespec-foundation-v5-2026-07-15": (
        "7fbf226b9b561aa4793120fa719517f2cbba5ee8bafbf09519078c01acc5aeff",
        "7d1f76b08431bad493822d6264480755f0768a3de67570a716df914595cf7317",
    ),
    "us-rulespec-snap-2026-07-21": (
        "88421cc4e4b93d253e03d8b679acb05faa843a75abae77cdf99ad25d69c3d898",
        "1d2cae04d8b83694e13756fe3302cda386272013b72818342dc0ccfb826a744a",
    ),
    "vn-rulespec-2026-07-24": (
        "88fa940a4122a59087f6b7a6d3cff4715211bfbe79e19c312b2135e99939023b",
        "8f0184addf2f4a7c7b2139a89f94a6de6aebaf9d055661b21f7fea08a5ae1d28",
    ),
    "vn-rulespec-2026-07-24-r2": (
        "c9d6b3f4b1a2561b9e2874f9eeab4ab50613eb709e97331f73ada479b421860c",
        "98981e1542c7b8c069dc98858a818c6c26f86ea29a2177ee0ef9d9a73799bbd1",
    ),
    "us-az-snap-ece-2026-10-23-manual-union": (
        "e9f69bf90ba5aaacaae969c20e5852c2dd1483fbc3fd3155ee10bd4bcba9f7e8",
        "78433f540ff7b037a449192885a10eff20d4cacdf7c157db4fd96e7cae348cc4",
    ),
    "us-rulespec-2026-10-13-w7-bundle-gaps-union": (
        "7d9605bbdc9cafaa8aa4b93c6646aae788f9bc376dd7941723e8f5d936caaa7f",
        "c09b3bbc62b9134612eb2ec1bb8bb90042da57cd5f6058f61408701674e38620",
    ),
}


@pytest.fixture(scope="module")
def selectors() -> dict[str, ReleaseManifest]:
    return load_tracked_selectors(_REPO_ROOT / "manifests" / "releases")


@pytest.fixture(scope="module")
def baseline() -> LineageBaseline:
    return LineageBaseline.load(_REPO_ROOT)


@pytest.mark.parametrize(
    ("base", "next_selectors", "newest"),
    [
        (
            "uk-rulespec-2026-08-07",
            ("uk-rulespec-2026-08-08",),
            "uk-rulespec-2026-11-02-uc-retirement-pension-income",
        ),
        (
            "uk-rulespec-2026-09-05",
            ("uk-rulespec-2026-09-06",),
            "uk-rulespec-2026-11-02-uc-retirement-pension-income",
        ),
        (
            "de-rulespec-2026-09-08-kindergeld-civil",
            (
                "de-rulespec-2026-09-08-kindergeld-context",
                "de-rulespec-2026-09-08-kindergeld-parentage",
            ),
            "de-rulespec-2026-09-09-kindergeld-bgb-amendment",
        ),
    ],
    ids=["issue-970-uk-copy", "mid-line-uk-copy", "recorded-de-copy"],
)
def test_a_copy_from_a_recorded_stale_base_is_a_fork_at_the_newest_head(
    selectors: dict[str, ReleaseManifest],
    baseline: LineageBaseline,
    base: str,
    next_selectors: tuple[str, ...],
    newest: str,
) -> None:
    copied = replace(
        selectors[base], name="lineage-stale-copy", description=f"Successor to {base}."
    )
    report = check_selector_lineage({**selectors, copied.name: copied}, baseline)
    forks = [finding for finding in report.forks if finding.predecessor == base]
    assert len(forks) == 1, report.problems()
    assert {copied.name, *next_selectors} <= set(forks[0].successors)
    assert newest in forks[0].heads


def _assert_reviewed_description_and_selector(
    selectors: Mapping[str, ReleaseManifest], name: str
) -> None:
    description_digest, selector_digest = _EVIDENCE_DIGESTS[name]
    actual_description_digest = hashlib.sha256(
        (selectors[name].description or "").encode("utf-8")
    ).hexdigest()
    assert actual_description_digest == description_digest, f"{name}: description evidence changed"
    assert selector_sha256(selectors[name]) == selector_digest, f"{name}: selected scopes changed"


@pytest.mark.parametrize(
    ("selector", "predecessor", "quote"), _EVIDENCE_EDGES, ids=[edge[0] for edge in _EVIDENCE_EDGES]
)
def test_recorded_successions_keep_the_reviewed_prose_and_both_selector_pins(
    selectors: dict[str, ReleaseManifest],
    baseline: LineageBaseline,
    selector: str,
    predecessor: str,
    quote: str,
) -> None:
    record = baseline.successions[selector]
    assert record.selector == selector
    assert record.predecessor == predecessor
    assert record.listed_on == _RECORDED_ON
    assert f'"{quote}"' in record.reason
    assert quote in (selectors[selector].description or "")
    for name in (selector, predecessor):
        _assert_reviewed_description_and_selector(selectors, name)
        assert baseline.selector_digests[name] == _EVIDENCE_DIGESTS[name][1]
        assert baseline.selector_digests[name] == selector_sha256(selectors[name])


def test_all_recorded_successions_quote_selector_prose_and_pin_both_sides(
    selectors: dict[str, ReleaseManifest], baseline: LineageBaseline
) -> None:
    recorded_today = {
        record.selector
        for record in baseline.successions.values()
        if record.listed_on == _RECORDED_ON
    }
    assert recorded_today == {selector for selector, _, _ in _EVIDENCE_EDGES}
    for record in baseline.successions.values():
        quotes = re.findall(r'"([^"\n]+)"', record.reason)
        assert quotes, f"{record.selector}: reason must quote its description"
        assert any(quote in (selectors[record.selector].description or "") for quote in quotes), (
            record
        )
        for name in (record.selector, record.predecessor):
            assert baseline.selector_digests[name] == selector_sha256(selectors[name])


@pytest.mark.parametrize(
    ("selector", "base", "quotes"),
    _PAIR_SCOPED_DERIVATIONS,
    ids=[entry[0] for entry in _PAIR_SCOPED_DERIVATIONS],
)
def test_pair_scoped_prose_bases_stay_first_cuts(
    selectors: dict[str, ReleaseManifest],
    baseline: LineageBaseline,
    selector: str,
    base: str,
    quotes: tuple[str, ...],
) -> None:
    for quote in quotes:
        assert quote in (selectors[selector].description or "")
    selected_pairs = {
        (scope.jurisdiction, scope.document_class) for scope in selectors[selector].scopes
    }
    base_pairs = {(scope.jurisdiction, scope.document_class) for scope in selectors[base].scopes}
    assert selected_pairs < base_pairs
    assert selector not in baseline.successions
    report = check_selector_lineage(selectors, baseline)
    assert report.predecessors[selector] is None
    assert baseline.first_cuts[selector].listed_on == "2026-11-02"
    for name in (selector, base):
        _assert_reviewed_description_and_selector(selectors, name)
    assert baseline.selector_digests[selector] == selector_sha256(selectors[selector])


@pytest.mark.parametrize(
    "name", ["uk-rulespec-2026-08-08", "uk-rulespec-2026-08-07"], ids=["selector", "predecessor"]
)
def test_editing_either_description_invalidates_the_reviewed_evidence(
    selectors: dict[str, ReleaseManifest], name: str
) -> None:
    changed = replace(selectors[name], description=f"{selectors[name].description} Edited prose.")
    assert selector_sha256(changed) == selector_sha256(selectors[name])
    with pytest.raises(AssertionError, match="description evidence changed"):
        _assert_reviewed_description_and_selector({**selectors, name: changed}, name)
