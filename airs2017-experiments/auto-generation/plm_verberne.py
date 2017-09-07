import json
import operator
import math
import re

topic_path = "../../airs2017-collection/topic/"

from elasticsearch import Elasticsearch
from elasticsearch import client

PORT = 9200
INDEX = "ussc"

es = Elasticsearch(urls='http://localhost', port=PORT, timeout=600)
es_client = client.IndicesClient(es)

class Term:
	def __init__(self, term, tf, mle, p_tc):
		self.term = term
		self.tf = tf
		self.p_td = mle
		self.p_tc = p_tc
		self.e_stp = 0
		self.converged = False

	def e_step(self, smooth_factor):
		self.e_stp = self.tf * ((smooth_factor * self.p_td)
			/ (((1 - smooth_factor) * self.p_tc) + (smooth_factor * self.p_td)))

	def m_step(self, term_pos, terms, inverse_d, iteration):
		sum_esteps = 0
		for i in range(len(terms)):
			if i != term_pos:
				sum_esteps += terms[i].e_stp

		new_p_td = self.e_stp / sum_esteps

		if (new_p_td < inverse_d) or ((abs(new_p_td - self.p_td) / self.p_td) < 0.05):
			self.converged = True

		self.p_td = new_p_td

def clean_text(text):
	return re.sub('[^a-zA-Z0-9]+', ' ', text).lower()

def get_numbers(text):
	nums = re.findall('[0-9]+', text)
	ret = ""
	for num in nums:
		ret = ret + num + " "
	return ret.rstrip()

def remove_stop(text):
	a_bod = {
		"analyzer": "stop",
		"text": text
	}
	non_stop_terms = {}
	non_stop_text = ""
	num_terms = 0
	res = es_client.analyze(index=INDEX, body=a_bod)
	for i in range(len(res["tokens"])):
		non_stop_terms[res["tokens"][i]["token"]] = True
		non_stop_text = non_stop_text + res["tokens"][i]["token"] + " "
		num_terms += 1
	return non_stop_text, num_terms, non_stop_terms

# -----------------------------------------------------------------------------

# take list of terms and return list of terms sorted by score ..
def plm(terms, num_terms, level):
	inverse_d = 1 / num_terms
	iteration = 0
	all_converged = False
	while not all_converged:
		print("Iteration -", iteration)

		for t in terms:
			if not t.converged:
				t.e_step(level)

		for i in range(len(terms)):
			if not terms[i].converged:
				terms[i].m_step(i, terms, inverse_d, iteration)

		all_converged = True
		for term in terms:
			if not term.converged:
				all_converged = False

		iteration += 1
		if iteration > 50:
			break

	term_list = []
	for term in terms:
		if term.p_td > 0.0001:
			term_list.append((term.term, term.p_td))

	term_list.sort(key=lambda x: x[1], reverse=True)

	sorted_terms = []
	for term in term_list:
		sorted_terms.append(term[0])

	return sorted_terms

# pass sorted terms
def write_proportions_to_file(terms, topic, method, level):
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

	terms_file = open("queries/" + str(topic) + "_" + method + "_" + str(int(round(level, 1) * 10)) + "_auto_query_terms.json", 'w')
	terms_file.write(json.dumps(js, indent=6))
	terms_file.close()


def generate_for_sentence(data, topic, level):
	sentence = data['citing_sentence']

	for j in range(len(data['case_extract'])):
		sentence = sentence.replace(data['case_extract'][j], "")
	sentence = clean_text(sentence)
	generate_for_text(sentence, topic, "plms", level)

def generate_for_para(data, topic, level):
	para = data['citing_paragraph']
	for j in range(len(data['case_extract'])):
		para = para.replace(data['case_extract'][j], "")
	para = clean_text(para)
	generate_for_text(para, topic, "plmp", level)

def generate_for_text(text, topic, run_type, level):
	non_stop_text, num_terms, _ = remove_stop(text)
	numbers = get_numbers(text)
	non_stop_text = non_stop_text + " " + numbers
	num_terms += len(numbers.split(' '))
	body = {
	"docs" : [
		{
			"_type": "decision",
			"doc" : {
				"plain_text" : non_stop_text
			},
			"term_statistics": True
			}
		]
	}
	res = es.mtermvectors(index=INDEX, body=body)
	sum_ttf = res["docs"][0]["term_vectors"]["plain_text"]["field_statistics"]["sum_ttf"]
	terms = []
	seen_terms = []
	for k, v in res["docs"][0]["term_vectors"]["plain_text"]["terms"].items():
		# Previously the stemmed token was being appended to the terms.
		# Now, match all of the occurrences of the term.
		for token in v['tokens']:
			# Uncomment this line to see what is happening.

			unstemmed_token = non_stop_text[token['start_offset']:token['end_offset']]
			if unstemmed_token not in seen_terms:
				ttf = 0

				# if no ttf in result ?? - then 1.
				if "ttf" not in v:
					ttf = 1
				else:
					ttf = v["ttf"]
				terms.append(Term(unstemmed_token, v["term_freq"], v["term_freq"]/num_terms, ttf/sum_ttf))
				seen_terms.append(unstemmed_token)

	sorted_terms = plm(terms, num_terms, level)
	write_proportions_to_file(sorted_terms, topic, run_type, level)

def main():
	for i in range(1, 101):
		f_name = topic_path + str(i) + ".json"

		with open(f_name) as file:
			data = json.load(file)
			l = 0.1
			while l <= 1:
				generate_for_sentence(data, i, l)
				generate_for_para(data, i, l)
				l += 0.1


if __name__ == '__main__':
	main()
