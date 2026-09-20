---
title: Giving robots a usable model of the world
date: 2026-08-15 09:00:00 +0900
category: Physical AI
tags:
  - robotics
  - knowrob
  - ontology
  - physical-ai
cover: /assets/images/uploads/스크린샷-2026-09-20-오후-6.26.52.png
excerpt: Perception tells a robot what it sees. Knowledge tells it what that
  means. The gap between the two is where most of the work is.
layout: post
---

A robot can detect a cup. Whether it knows a cup can hold liquid, tips over, and belongs on
a table — that's a different system entirely.

## Perception is not understanding

Modern perception is excellent at labels and poor at consequences. **Physical AI** is the
attempt to close that gap: to give an agent structured knowledge it can reason over, not
just a stream of detections.

## Ontologies as the substrate

Frameworks like **KnowRob** represent objects, affordances, and actions as a queryable
knowledge base. The robot asks questions — *what can I do with this? what happens if I
tip it?* — and gets answers grounded in an explicit model rather than a black box.

It's unfashionable next to end-to-end learning, but for anything that has to act safely in
the real world, an inspectable model of *why* is worth a lot. Ongoing notes live in
[knowrob_OPAL](https://github.com/ValleyJin/knowrob_OPAL).
