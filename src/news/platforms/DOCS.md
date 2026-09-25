# src/news/platforms/

## Role

Namespace package holding one subdirectory per news source, each implementing the platform protocol from src/news. No logic lives at this level. Touch it only to add a new platform directory; change discovery or cleanup inside the platform's own subdirectory.

## Public Interface

`__init__.py` is empty. Each platform subpackage exports its platform class; src/news/registry.py lists the classes.

## Flow

The registry instantiates the platform class matching the source name. The workflow modules then drive the platform through discover, dedup, scrape and, for the proxy-pool engine, clean pass.

## Modules

This directory contains no modules of its own; see coindesk/ and theblock/.

## State

None.
