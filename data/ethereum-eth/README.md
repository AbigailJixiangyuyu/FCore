# Ethereum

This FCore sample contains 15,869 positive-value ETH transfers between addresses on Ethereum Mainnet. The 13 weekly snapshots cover October 5, 2015 through January 3, 2016 (UTC). The monitored cohort has 89 addresses. Of these, 75 interacted with another cohort address during the demonstration period.

## Source and attribution

Can Özturan, Alper Şen and Baran Kılıç published *Transaction Graph Dataset for the Ethereum Blockchain*, version 2, on Zenodo under CC BY 4.0. FCore joins two of their files, selects a period and cohort, gives the addresses short identifiers and projects the transfers to an undirected graph. [Dataset and download](https://doi.org/10.5281/zenodo.4718440) · [License](https://creativecommons.org/licenses/by/4.0/) · [Kılıç, Özturan and Sen, *Cluster Computing*, 2022](https://doi.org/10.1007/s10586-021-03511-0)

The source includes block and transaction positions, asset, sender, recipient and value, plus a block-time table. FCore keeps successful native ETH transfers of positive value between distinct, nonzero addresses. Block rewards, failed transfers and contract creation have no entries in the sample. A retained address may be controlled by a person, an exchange or a smart contract. The source supplies no fraud labels for this cohort.

## Sampling and snapshot semantics

1. Use the four weeks from September 7 to October 5, 2015 (end exclusive) to form an undirected simple graph from eligible transfers. Rank addresses by descending coreness, then descending distinct-neighbor count, then ascending address. Freeze the first 89 before S01. This sampling favors connected addresses for community search.
2. Sort the 89 addresses lexicographically and assign E001 through E089. The reversible mapping and source checksums are in [provenance.json](provenance.json).
3. Take every eligible transfer between those addresses during the next 13 weeks. One CSV row is one original transfer, including repeated interactions and tied timestamps. The two endpoints are unordered in FCore. The timestamp is the original block's Unix time in seconds. All cohort members remain in the roster, even in weeks without an internal transfer for that address.

| Stage | Snapshots | Transfers |
| --- | --- | ---: |
| Historical mining and model training | S01–S11 | 13,609 |
| Current search and scoring | S12 | 1,159 |
| Held-out observation | S13 | 1,101 |

S12 (December 21–27 UTC) has 47 active addresses and 68 distinct internal links in the full cohort. Query E025 at k=2 to find a community with 27 addresses and 50 links. E025 has the most distinct cohort neighbors over S01–S11. The default historical fixed-window query returns a 3-core with 12 addresses and 24 internal links over S10–S11. All six historical methods have dataset-specific defaults. [Query configuration](../../config/query-defaults.json)

With the same E025 and k=2, historical periodic mining returns 23 addresses. Their induced graph satisfies the core condition in S04–S05, S07–S08 and S10–S11. Comparing that selection with the current community yields 22 retained, 5 added and 1 absent. S12 SLADE scores are computed from the sample's observed transfers. They measure unusual interactions within the monitored cohort.

With E025, k=2 and edge probability above 0.50, Zebra predicts that all 27 current members will be retained in S13. At the S14 horizon it predicts 26 retained, one added and one exited. Both predictions use observations through S12. SLADE scores and all three Zebra horizons have also been checked using CPU inference.

## Reproduce

The packaged CSVs suffice to run the demo. To rebuild, download the two files below into `data/raw/ethereum-zenodo-4718440/` and run the commands from the `demo/` directory. The converter checks both original file hashes before writing the sample. [Transfer file, 41.5 MB](https://zenodo.org/records/4718440/files/eth-tx-0-999999.txt.bz2?download=1) · [Block times, 4.5 MB](https://zenodo.org/records/4718440/files/eth-blocktime-0-999999.txt.bz2?download=1)

```powershell
uv run --no-sync --directory backend python -m scripts.import_ethereum
uv run --no-sync --directory backend python -m scripts.train_slade --dataset ethereum-eth
uv run --no-sync --directory backend python -m scripts.train_zebra --dataset ethereum-eth
uv run --no-sync --directory backend python -m scripts.calibrate_links --dataset ethereum-eth --model zebra
uv run --no-sync --directory backend python -m scripts.train_zebra --dataset ethereum-eth --horizon 2
uv run --no-sync --directory backend python -m scripts.train_zebra --dataset ethereum-eth --horizon 3
```

## Other public financial data considered

- TGB's `tgbl-coin` also records address-to-address transfers and supports link prediction. The published benchmark has 638,486 addresses and 22,809,486 edges across five stablecoins and one wrapped token, under a CC BY-NC license. [Temporal Graph Benchmark](https://tgb.complexdatalab.com/docs/linkprop/#dataset-tgbl-coin-leaderboard)
- Sarafu records payments in a Kenyan community currency with pseudonymous sender, receiver and time. Access to the research dataset requires registration and its reuse is governed by the UK Data Service End User Licence. [Data repository](https://reshare.ukdataservice.ac.uk/855142/) · [Scientific Data paper](https://www.nature.com/articles/s41597-022-01539-4)
