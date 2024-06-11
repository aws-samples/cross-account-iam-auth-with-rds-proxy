# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

setup:
	mkdir assets/layers/psycopg2/python
	pip install psycopg2-binary --target assets/layers/psycopg2/python
	zip -r layer.zip assets/layers/psycopg2/python
	rm -r assets/layers/psycopg2/python
