# Glider
_Adam Krivka_

This is a personal note-taking-ish app centered around the time-dimension.

## Motivation

TODO

## Description

Glider attempts to combine note-taking, journaling, calendar and data collection. The key idea is that most apps miss the time dimension in all of these things (well, except calendar). When you edit a note, it should be a _new note_ and a record of the old version should be kept. This is not the case for most note-taking apps since this is not scalable for many users. 

Glider is meant to be run on a machine/compute you own. There is no end-to-end encryption and no multi-user features. 

Glider also sacrifies some other nice-to-haves in note-taking apps in order to focus on innovating on the other things, namely it doesn't attempt to be local-first, opting instead for a simple traditional server/client architecture, and doesn't aim for a native experience on all devices - it's a simple web app (for now).

Another goal of Glider is to be a sort of self-surveillance tool. First, you connect your social media, calendar, review app, ... services and Glider periodically pulls data from there to a central location. Second, Glider acts as a view engine for all this data. 

## Architecture

The frontend uses SvelteKit and the backend is written in Python. This is mostly due to which technologies I'm familiar with.

## Inspiration

* https://julian.digital/2023/07/06/multi-layered-calendars/