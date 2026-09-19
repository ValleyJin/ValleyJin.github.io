---
layout: post
title: "What an L2 actually has to get right"
date: 2026-08-28 09:00:00 +0900
category: Blockchain
tags: [ethereum, l2, tokamak, infrastructure]
cover: /assets/images/3D_Block.jpeg
excerpt: "Rollups are easy to describe and hard to operate. A short list of the parts that decide whether an L2 is trustworthy."
---

"An L2 posts transactions to Ethereum and inherits its security" is the elevator pitch.
Operating one is a longer conversation.

## The parts that matter

1. **Data availability** — if the data behind a state root isn't recoverable, users can't
   exit. This is the whole game.
2. **The bridge** — the contract holding funds is the highest-value target on the stack.
   It should be boring, audited, and minimal.
3. **Sequencing** — someone orders transactions. Centralized sequencers are a pragmatic
   start and a decentralization to-do.
4. **Proving** — fraud proofs or validity proofs are what make the "inherits security"
   claim real rather than aspirational.

Working inside the [Tokamak Network](https://github.com/tokamak-network) ecosystem, the
launch tooling around these pieces is as important as the pieces themselves — most teams
don't fail at cryptography, they fail at operations.
