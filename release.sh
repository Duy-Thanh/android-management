#!/bin/env bash

git tag -d v2.0.1
git tag v2.0.1

git push origin v2.0.1 -f
