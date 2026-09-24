# src/news/platforms/

## Role

Namespace package holding one subdirectory per news source, each implementing the platform protocol from src/news. No logic lives at this level. Touch it only to add a new platform directory; change discovery or cleanup inside the platform's own subdirectory.

## Public Interface

`__init__.py` is empty. Each platform subpackage registers its implementation as a side effect of being imported by src/news/__main__.py.

## Flow

The news entry point imports a platform subpackage, which instantiates and registers its implementation. The pipeline then looks the platform up by source name and drives discover, dedup, scrape and, for the proxy-pool engine, clean pass.

## Modules

This directory contains no modules of its own; see coindesk/ and theblock/.

## State

None.
