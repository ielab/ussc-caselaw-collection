
import json
import os 

doc_path = "../airs2017-collection/docs" 


def get_av_num_words():
	# num_words = 0
	num_citations = 0
	files = os.listdir(doc_path)
	num_files = len(files) 

	for f in files:
		if not f.startswith('.') and os.path.isfile(os.path.join(doc_path, f)):
			f_name = doc_path + "/" + f
			with open(f_name) as file:

				data = json.load(file)


				num_words += len(data["plain_text"].split(' '))


	return num_words / num_files

def main():
	print(get_av_num_words())


if __name__ == '__main__':
	main()
