import json
import re
from decimal import *

from elasticsearch import Elasticsearch

PORT = 9200
INDEX = "ussc"

localhost = "http://localhost"
local_port = 9200 
doctype = "decision"
coll_field = "plain_text"

background_index = "clueweb12b_all"
background_coll_host  = "http://SEF-IS-017660" 
background_coll_port = 9200 
background_coll_doctype = "clueweb"
background_collection_field = "body"

back_coll_inv_tf = 1 / 48555251

topic_path = "/Users/danlocke/go/src/ussc-queries/topic/"
server_topic_path = "/Users/danlocke/phd/ussc-queries/topic/"

# Change for local or server 
es = Elasticsearch(urls=localhost, port=PORT, timeout=600)

class Term:
	def __init__(self, term, tf):
		self.term = term
		self.tf = tf


def clean_text(text):
  clean_text = re.sub('[^a-zA-Z0-9.]+', ' ', text)
  return clean_text

def get_tf(index, text, doc_type, field):
	body = {
		"docs" : [
			{
				"_type": doc_type,
					"doc" : {
					  field : text
					},  
				"term_statistics": True
			}
		]
	}
	res = es.mtermvectors(index=index, body=body)
	if 'sum_ttf' not in res['docs'][0]['term_vectors'][field]['field_statistics']:
		print("sum ttf not in res")
		print(res)
	sum_ttf = res['docs'][0]['term_vectors'][field]['field_statistics']['sum_ttf']	
	
	terms = []
	for k, v in res['docs'][0]['term_vectors'][field]['terms'].items():
		term = k
		ttf = 0
		if "ttf" in v: 
			ttf = v["ttf"]
			tf = Decimal(v["ttf"]) / Decimal(sum_ttf)
		else: 
			print("Ttf not in return for term -", k, "-", v, "for query -", text)
			tf = back_coll_inv_tf
		terms.append(Term(term, tf))

	return terms 

def get_collection_terms_tf(coll_name, doc_type, field):
	terms = {}
	coll_term_file = coll_name + "_topics_tf.txt"

	# for each topic
	for i in range(1, 101):
		print("Topic -", i, "----------------")
		f_name = topic_path + str(i) + ".json"
		# f_name = server_topic_path + str(i) + ".json"

		q_terms = []

		with open(f_name) as file:
			data = json.load(file)

			for i in range(len(data['query'])):
				text = data['query'][i]
				text = text.replace("AND", "", -1)
				text = text.replace("OR", "", -1)
				text = text.replace("(", "", -1)
				text = text.replace(")", "", -1)
				text = text.replace("\"", "", -1)

				q_terms.append(get_tf(coll_name, text, doc_type, field))

			keywords = ""
			for i in range(len(data['relevant_keywords'])):
				keywords = keywords + data['relevant_keywords'][i] + " "

			q_terms.append(get_tf(coll_name, keywords, doc_type, field))

			sentence = data['citing_sentence']
			for j in range(len(data['case_extract'])):
				sentence = sentence.replace(data['case_extract'][j], "")
			sentence = clean_text(sentence)


			q_terms.append(get_tf(coll_name, sentence, doc_type, field))

			para = data['citing_paragraph']
			for j in range(len(data['case_extract'])):
				para = para.replace(data['case_extract'][j], "")
			para = clean_text(para)

			q_terms.append(get_tf(coll_name, para, doc_type, field))

			for term in q_terms:
				for t in term:
					if t.term not in terms: 
						terms[t.term] = t.tf

			q_terms = []


	print(len(terms))
	out_file = open(coll_term_file, "w")
	for k, v in terms.items():
		out_file.write(k + " " + str(v) + "\n")

	out_file.close()

	terms = {}
	

def main():
	get_collection_terms_tf(INDEX, doctype, coll_field)
	# get_collection_terms_tf(background_index, 
	# 	background_coll_doctype, background_collection_field)

if __name__ == '__main__':
	main()