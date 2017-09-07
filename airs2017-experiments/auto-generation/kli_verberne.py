
# You want to apply some filtering (e.g. NP) - but also see what happens
# if you don't do this. Then you want to score the keywords and extract
# the highest ranked keywords (in this way you can form queries from 1 to
# $n$ terms long, thus studying the influence of more verbose queries).
# In particular, use PLM, KLI, C-value, KLP (and consider putting together
# importance and phraseness, ie KLI+KLP = KLIP -- ask Jimmy to get the scores
# for clueweb as background collection). You can even use BM25 scores

import re
import math
import json

topic_path = "../../airs2017-collection/topic/"

from elasticsearch import Elasticsearch
from elasticsearch import client

PORT = 9200
INDEX = "ussc"

es = Elasticsearch(urls='http://localhost', port=PORT, timeout=600)
es_client = client.IndicesClient(es)


coll_map = {}
back_coll_map = {}

# index 1/|C| for back_coll
inv_back_coll_term_count = 1 / 24840204976
inv_index_term_count = 1/ 121926826

class Term:
	def __init__(self, term, score):
		self.term = term
		self.score = score

def clean_text(text):
	return re.sub('[^a-zA-Z0-9]+', ' ', text).lower()

def get_numbers(text):
  nums = re.findall('[0-9]+', text)
  seen = set()
  ret = ""
  for num in nums:
      if num not in seen:
          seen.add(num)
          ret = ret + num + " "
  return ret.lstrip().rstrip()

def remove_stop(text):
	a_bod = {
		"analyzer": "stop",
		"text": text
	}
	final_text = ""
	res = es_client.analyze(index=INDEX, body=a_bod)
	for i in range(len(res["tokens"])):
		final_text = final_text + " " + res["tokens"][i]["token"]
	return final_text

def get_n_grams(sentence, n, bool_query):
	# Clean boolean query
	if bool_query == True:
		sentence = sentence.replace("AND", "", -1)
		sentence = sentence.replace("OR", "", -1)
		sentence = sentence.replace("(", "", -1)
		sentence = sentence.replace(")", "", -1)
		sentence = sentence.replace("\"", "", -1)

	sentence = sentence.split(' ')
	output = []
	for i in range(len(sentence)-n+1):
		temp = ""
		for j in range(i, i+n):
			temp += sentence[j] + " "
		output.append(temp.rstrip(' '))
	return output

# -----------------------------------------------------------------------------

def kli_d(p_td, p_tc):
	return p_td * math.log10(p_td / p_tc)


def kli_div(terms):

	# take list of terms ..
	coll_term_scores = []
	back_term_scores = []

	for i in range(len(terms)):
		if terms[i] in coll_map:
			coll_term_scores.append((terms[i], i, float(coll_map[terms[i]])))
		else:
			print("Term not in collection scores map -", terms[i])
			coll_term_scores.append((terms[i], i, inv_index_term_count))

		if terms[i] in back_coll_map:
			back_term_scores.append((terms[i], i, float(back_coll_map[terms[i]])))
		else:
			# for terms not in C we estimate as 1/|C|
			print("Term not in background collection scores map -", terms[i])
			back_term_scores.append((terms[i], i, inv_back_coll_term_count))

	# KLI = P(t|D) * log(P(t|D) / P(t|C))
	kli_terms = []
	for i in range(len(coll_term_scores)):
		kli = kli_d(coll_term_scores[i][2], back_term_scores[i][2])
		kli_terms.append((terms[coll_term_scores[i][1]], kli))

	kli_terms.sort(key=lambda x: x[1])
	# print("sorted terms")

	sorted_terms = []
	for t in kli_terms:
		sorted_terms.append(t[0])

	return sorted_terms



def generate_auto_proportion_for_text(text, topic, method):
	body = {
	"docs" : [
		{
			"_type": "decision",
			"doc" : {
				"plain_text" : text
			},
			"term_statistics": True
			}
		]
	}
	res = es.mtermvectors(index=INDEX, body=body)
	term_mapping = {}
	for k, v in res["docs"][0]["term_vectors"]["plain_text"]["terms"].items():
		# Previously the stemmed token was being appended to the terms.
		# Match all of the occurrences of the term.
		for token in v['tokens']:
			# Uncomment this line to see what is happening.
			if k not in term_mapping:
				term_mapping[k] = set()
			term_mapping[k].add(text[token['start_offset']:token['end_offset']])

	# Create the filtered list of stemmed tokens
	kli_terms = kli_div(list(term_mapping.keys()))
	# Map, filter and flatten the terms into the new, mapped list
	mapped_terms = [i for s in [term_mapping[x] for x in kli_terms if x in term_mapping] for i in s]

	write_proportions_to_file(mapped_terms, topic, method)

# pass sorted terms
def write_proportions_to_file(terms, topic, method):
	# proportion varied from 1/|D| to 1 where |D| was the total number of terms
	inverse_d = 1 / len(terms)

	proportions = []

	js = {"auto_generated_queries":{"topic": topic, "query":[]}}

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

		js["auto_generated_queries"]["query"].append({"proportion": inverse_d, "terms": proportion_terms})

	terms_file = open("queries/" + str(topic) + "_" + method + "_auto_query_terms.json", 'w')
	terms_file.write(json.dumps(js, indent=6))
	terms_file.close()

def generate_for_sentence(data, topic):
	sentence = data['citing_sentence']
	for j in range(len(data['case_extract'])):
		sentence = sentence.replace(data['case_extract'][j], "")
	sentence = clean_text(sentence)
	numbers = get_numbers(sentence)
	final_sentence = remove_stop(sentence)
	final_sentence = final_sentence + " " + numbers
	generate_auto_proportion_for_text(final_sentence, topic, "klis")

def generate_for_para(data, topic):
	para = data['citing_paragraph']
	for j in range(len(data['case_extract'])):
		para = para.replace(data['case_extract'][j], "")
	para = clean_text(para)
	numbers = get_numbers(para)
	para = remove_stop(para)
	para = para + " " + numbers
	generate_auto_proportion_for_text(para, topic, "klip")


def main():

	# open both files.. into maps.
	with open("ussc_topics_tf.txt") as file:
		for f in file.readlines():
			coll_map[f.split()[0]] = f.split()[1]

	with open("clueweb12b_all_topics_tf_except_not_found.txt") as file:
		for f in file.readlines():
			back_coll_map[f.split()[0]] = f.split()[1]

	for i in range(1, 101):
		f_name = topic_path + str(i) + ".json"

		with open(f_name) as file:
			data = json.load(file)
			generate_for_sentence(data, i)
			generate_for_para(data, i)


if __name__ == '__main__':
	main()
