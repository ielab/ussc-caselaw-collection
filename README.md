# ussc-caselaw-collection

# Collection
To create the collection: 
1. Download and extract https://www.courtlistener.com/api/bulk-data/opinions/scotus.tar.gz and https://www.courtlistener.com/api/bulk-data/clusters/scotus.tar. The final document in the collection that we used was BSNF Railway Co. v Tyrell (id 4172500).
2. go get, build and run with input flags for opinions and cluster paths, `airs2017-collection/ussc.go`.

The mapping for the documents is as follows: 

```index_request = {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0,
      "analysis": {
        "analyzer": {
            "ussc-standard": {
                "tokenizer": "standard",
                "filter": ["lowercase", "terrier_stopwords", "porter_stem"]
            }
        },
        "filter": {
          "terrier_stopwords": {
              "type": "stop",
              "stopwords_path": PATH_TO_EMPTY_STOPWORDS_FILE.txt
          }
        }
      },
      "similarity": {
        "ussc_name": {
            "type": "BM25",
            "b": 0.75,
            "k1": 1.2
        },
        "ussc_text": {
            "type": "BM25",
            "b": 0.75,
            "k1": 1.2
        }
      }
    },

    "mappings": {
        DOCUMENT: {
            "_source": {
                "enabled": True
            },
            "properties": {
                "case_name": {
                    "type": "text",
                    "similarity": "ussc_name",
                    "analyzer": "ussc-standard",
                     "fields": {
                        "length": {
                            "type": "token_count",
                            "store": "yes",
                            "analyzer": "whitespace"
                        }
                     }
                },
                "date_filed": {
                    "type": "date",
                    "format":"yyyy-MM-dd||epoch_millis"
                },
                "plain_text": {
                    "type": "text",
                    "similarity": "ussc_text",
                    "analyzer": "ussc-standard",
                     "fields": {
                        "length": {
                            "type": "token_count",
                            "store": "yes",
                            "analyzer": "whitespace"
                        }
                     }
                }, 
                "html": {
                    "type": "text",
                    "similarity": "ussc_text",
                    "analyzer": "ussc-standard",
                     "fields": {
                        "length": {
                            "type": "token_count",
                            "store": "yes",
                            "analyzer": "whitespace"
                        }
                     }
                }
            }
        }
    }
}```

As per our paper, no stopwords were used. 

Topics are contained in `airs2017-collection/topic`. An example is as per below:
```
{
  "id": 2,
  "case_id": 4172500,
  "case_title": "BNSF R. Co. v. Tyrrell",
  "date_filed": "2017-05-30",
  "html": "..."",
  "plain_text": "",
  "cited_id": [
    103549
  ],
  "id_manually_found": [
    false
  ],
  "cited_case": [
    "Baltimore \u0026 Ohio R. Co. v. Kepner, 314 U. S. 44 (1941)"
  ],
  "case_extract": [
    "Baltimore \u0026 Ohio R. Co. v. Kepner, 314 U. S. 44 (1941)"
  ],
  "citing_sentence": "",
  "relevant_keywords": [...],
  "query": [...],
  "es_query" : [...]
}```

QRELS are either '1' for a relevant decision or '3' for a cited decision in the topic sentence. No distinction was taken in the paper. 

# Experiments and Results
Code to auto generate queries for proportions, r, can be found in 'airs2017-experiments/auto-generation'. An instance of Elasticsearch needs to be specified, and running. Collection statistics for the background collection, clueweb_12b_all, that was used for calculating KLI is provided, as well as a script to generate the statistics for a given background collection. Auto-generated queries will be created in 'airs2017-experiments/auto-generation/queries'.

Following creation of the automatic-queries, to evaluate:
1. run 'airs2017-experiments/create_run_file.py' which generates the run_file
2. run 'airs2017-experiments/trec_eval.py' - this will generate csv files for each run in 'results/res_files'

The Jupyter notebooks in 'airs2017-experiments/results' provide for the analysis in the paper. 

# Paper
A copy of our preprint paper is available in 'airs2017-paper'.

# Setup and required 
- Golang (version 1.8.1 used)
- Elasticsearch (version 5.4.2 used)
- Python 3 (version 3.6 used)
- Jupyter (pip3 install jupyter)
- Trec Eval (version 9.0 used)
