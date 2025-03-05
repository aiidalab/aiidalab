#!/bin/bash

jinja2 --format=yaml terms-of-use.j2 config.yaml > terms-of-use.html
jinja2 --format=yaml privacy-policy.j2 config.yaml > privacy-policy.html
