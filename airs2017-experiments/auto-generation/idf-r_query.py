# Daniel Locke, 2017
import json
import math
import os
import operator
import re

from elasticsearch import Elasticsearch
from elasticsearch import client

PORT = 9200
INDEX = "ussc"
topic_path = "../../airs2017-collection/topic/"

es = Elasticsearch(urls='http://localhost', port=PORT, timeout=600)

es_client = client.IndicesClient(es)

class Coll_stats:
  def __init__(self, doc_count, total_terms):
    self.total_terms = total_terms
    self.doc_count = doc_count

class Term:
  def __init__(self, term, idf, col_freq, doc_freq):
    self.term = term
    self.idf = idf
    self.col_freq = col_freq
    self.doc_freq = doc_freq

class AutoQuery:
  def __init__(self, terms, proportion, av_idf, av_ictf, av_scq):
    self.terms = terms
    self.proportion = proportion
    self.av_idf = av_idf
    self.av_ictf = av_ictf
    self.av_scq = av_scq

# Clean text consistent with the cleaning used for the indexed plain_text
def clean_text(text):
  return re.sub('[^a-zA-Z0-9]+', ' ', text).lower()

def get_numbers(text):
  return re.sub('[^0-9]+', ' ', text).lstrip().rstrip()

def remove_stop(text):
  a_bod = {
    "analyzer": "stop",
    "text": text
  }
  final_text = ""
  res = es_client.analyze(index=INDEX, body=a_bod)
  for i in range(len(res["tokens"])):
    final_text = final_text + res["tokens"][i]["token"] + " " 
  return final_text

# Returns list of terms and idf, sorted from highest to lowest
def get_idf(body, index_doc_count, text):
  res = es.mtermvectors(index=INDEX, body=body)
  collection_num_terms = res["docs"][0]["term_vectors"]["plain_text"]["field_statistics"]["sum_ttf"]

  coll_stats = Coll_stats(index_doc_count, collection_num_terms)
  terms = []
  seen_terms = []
  for k, v in res["docs"][0]["term_vectors"]["plain_text"]["terms"].items():
    idf = 1 / 63916
    if "ttf" in v:
      term = k 
      col_freq = v["ttf"]
      doc_freq = v["doc_freq"]

      idf = math.log10((1 + index_doc_count)/ doc_freq)
      
    else:
      print(k, "- ttf not returned for term in query ")

    for token in v['tokens']:
      unstemmed_token = text[token['start_offset']:token['end_offset']]
      print(k, unstemmed_token)
      if unstemmed_token not in seen_terms:
        terms.append(Term(unstemmed_token, idf, col_freq, doc_freq))
        seen_terms.append(unstemmed_token)

  terms.sort(key=operator.attrgetter('idf'), reverse=True)

  return terms, coll_stats


# Eval terms for ... 
def eval(coll_stats, terms):
  num_terms = len(terms)
  sum_ictf = 0 
  sum_idf = 0 
  sum_scq = 0

  for term in terms:
    sum_idf += term.idf
    
    # log2 n(w)/ T where T is the total number of terms in the collection.
    ictf = math.log((term.col_freq/ coll_stats.total_terms), 2)
    sum_ictf += ictf

    # SCQw =  where Nw is the document frequency of w
    scq = (1 + math.log(term.col_freq / coll_stats.doc_count)) * math.log(1 + (coll_stats.doc_count/term.doc_freq))
    sum_scq += scq

  av_idf = sum_idf / num_terms
  av_ictf = sum_ictf / num_terms
  av_scq = sum_scq / num_terms
  return av_idf, av_ictf, av_scq

def generate_res_for_query(text, data, idc):
  t = text

  body = {
    "docs" : [
      {
        "_type": "decision",
        "doc" : {
          "plain_text" : t
        },  
        "term_statistics": True
      }
    ]
  }
  terms, coll_stats = get_idf(body, idc, text)
  return eval(coll_stats, terms)


def generate_q_for_text(text, data, idc):
  t = text
   
  for j in range(len(data['case_extract'])):
    t = t.replace(data['case_extract'][j], "")
  t = clean_text(t)

  numbers = get_numbers(t)
  final_text = remove_stop(t)
  final_text = final_text + " " + numbers
  body = {
    "docs" : [
      {
        "_type": "decision",
        "doc" : {
          "plain_text" : final_text
        },  
        "term_statistics": True
      }
    ]
  }
  terms, coll_stats = get_idf(body, idc, final_text)
  
  # proportion varied from 1/|D| to 1 where |D| was the total number of terms 
  inverse_d = 1 / len(terms)
  proportions = []

  num_token = len(terms)
  ideal = 0.1
  for i in range(0, 11):
    num_terms = math.ceil(inverse_d * num_token)
    if inverse_d < ideal:
      inverse_d += 0.1
    if inverse_d >= 1:
      inverse_d = 1
    
    ideal += 0.1

    proportion_terms = terms[0: num_terms]
    
    av_idf, av_ictf, ac_scq = eval(coll_stats, proportion_terms)

    proportions.append(AutoQuery(proportion_terms, inverse_d, av_idf, av_ictf, ac_scq))
    
    proportions

  return proportions  

def generate_q_for_sentence(topic, data, idc):
  sentence = data['citing_sentence']
  proportions = generate_q_for_text(sentence, data, idc)

  terms = {"auto_generated_queries":{"topic": topic, "query":[]}}

  for proportion in proportions:
    p_terms = []
    for term in proportion.terms:
      p_terms.append(term.term)

    terms["auto_generated_queries"]["query"].append({"proportion": proportion.proportion, "terms": p_terms})

  terms_file = open("../auto-generation/queries/" + str(topic) + "_idfs_auto_query_terms.json", 'w')
  terms_file.write(json.dumps(terms, indent=6))
  terms_file.close()


def generate_q_for_para(topic, data, idc):
  para = data['citing_paragraph']
  proportions = generate_q_for_text(para, data, idc)

  terms = {"auto_generated_queries":{"topic": topic, "query":[]}}

  for proportion in proportions:
    p_terms = []
    for term in proportion.terms:
      p_terms.append(term.term)

    terms["auto_generated_queries"]["query"].append({"proportion": proportion.proportion, "terms": p_terms})

  terms_file = open("queries/" + str(topic) + "_idfp_auto_query_terms.json", 'w')
  terms_file.write(json.dumps(terms, indent=6))
  terms_file.close()

def generate_res_for_ad_hoc_queries(topic, data, idc):
  for i in range(len(data['query'])):
    text = data['query'][i]
    text = text.replace("AND", "", -1)
    text = text.replace("OR", "", -1)
    text = text.replace("(", "", -1)
    text = text.replace(")", "", -1)
    text = text.replace("\"", "", -1)

    proportion = generate_res_for_query(text, data, idc)
    sentence = str(topic) + " q " + str(i) + " " + str(proportion[0]) + \
     " " + str(proportion[1]) + " " +  str(proportion[2]) + "\n"
    print(sentence)
      
def main():

  ind_stats = es.indices.stats()
  index_doc_count = ind_stats["indices"]["ussc"]["primaries"]["docs"]["count"]
  for i in range(1, 101):
    f_name = topic_path + str(i) + ".json"

    with open(f_name) as file:
      data = json.load(file)

      # Uncomment and do each of these...
      print("TOPIC", i , "---------------")
      generate_q_for_sentence(i, data, index_doc_count)
      generate_q_for_para(i, data, index_doc_count)

if __name__ == '__main__':
  main()



