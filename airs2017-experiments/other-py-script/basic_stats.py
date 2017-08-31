import os
import json




topic_path = "../airs2017-collection/topic/"


def main():

	num_queries = 0
	num_assessments = 0

	f_name = "../ussc-queries/assessments.json"
	
	with open(f_name) as file:
		data = json.load(file)

		for topic in data:
			# print(topic)
			for assessment in topic["assessments"]:
				num_assessments += 1

	for i in range(1, 101):
		t_f_name = topic_path + str(i) + ".json"
		with open(t_f_name) as topic_file:
			data = json.load(topic_file)
			num_queries +=len(data["query"])

	print("Number queries:", num_queries)
	print("Number assessments:", num_assessments)

if __name__ == '__main__':
	main()
