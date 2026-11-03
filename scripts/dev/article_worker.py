#!/usr/bin/env python3
"""Dedicated lifecycle worker; R6 deploys this independent process."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"workers/ingestion-python/src"))
from autodata_ingestion.worker import article_worker_main

if __name__=="__main__":raise SystemExit(article_worker_main())
