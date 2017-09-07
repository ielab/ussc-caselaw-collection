package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
	"unicode"

	"github.com/levigross/grequests"
)

const run_file_path string = "run-files/"
const run_f_name string = "_res_file.txt"

const topic_path string = "../airs2017-collection/topic/"
const auto_gen_methods_path string = "auto-generation/queries/"

const PORT int = 9200
const INDEX string = "ussc"

const NUM_RESULTS int = 1000

type ElasticSearchResponse struct {

	Took float64 `json:"took"`

	Timed_out bool `json:"timed_out"`

	Shards struct {

		Total int64 `json:"total"`

		Successful int64 `json:"successful"`

		Failed int64 `json:"failed"`

	} `json:"_shards"`

	Hits struct {

		Total int64 `json:"total"`

		MaxScore float64 `json:"max_score"`

		Hits []SearchHit `json:"hits"`

	} `json:"hits"`
}

type SearchHit struct {

	Index string `json:"_index"`

	Type string `json:"_type"`

	Id string `json:"_id"`

	Score float64 `json:"_score"`

}

type ElasticStopwordResponse struct {

	Tokens []StopwordToken `json:"tokens"`

}

type StopwordToken struct {

	Token string `json:"token"`

	Start int64 `json:"start_offset"`

	End int64 `json:"end_offset"`

	Type string `json:"type"`

	Position int64 `json:"position"`

}

type Result struct {

	Topic string

	Id string

	Rank string

	Score string

	RunName string

}

type Topic struct {

	Id int `json:"id"`

	CaseId int `json:"case_id"`

	CaseTitle string `json:"case_title"`

	DateFiled string `json:"date_filed"`

	Html string `json:"html"`

	PlainText string `json:"plain_text"`

	CitedId []int `json:"cited_id"`

	IdFound []bool `json:"id_manually_found"`

	CitedCase []string `json:"cited_case"`

	CaseExtract []string `json:"case_extract"`

	CitingSentence string `json:"citing_sentence"`

	CitingParagraph string `json:"citing_paragraph"`

	RelevantKeywords []string `json:"relevant_keywords"`

	Query []string `json:"query"`

	EsQuery []map[string]interface{} `json:"es_query"`

}

type ProportionFile struct {

	Content struct {

		Topic int64 `json:"topic"`

		Query []struct {

			Proportion float64 `json:"proportion"`

			Terms []string `json:"terms"`

		} `json:"query"`

	} `json:"auto_generated_queries"`

}


func open(file string) *os.File {
	_, err := os.Stat(file)
	if err == nil {
		err = os.Remove(file)
		if err != nil {
			log.Fatal(err)
		}
	}
	f, err := os.OpenFile(file, os.O_CREATE|os.O_RDWR, 0666)
	if err != nil {
		log.Fatal(err)
	}
	return f
}


func removeStop(text string) string {
	body := map[string]interface{}{
		"analyzer": "stop",
		"text": text,
	}

	ro := &grequests.RequestOptions{
		JSON: body,
	}
	es_response, err := grequests.Post("http://localhost:9200/ussc/_analyze", ro)
	if err != nil {
		log.Panicln(err)
	}

	if es_response.StatusCode != 200 {
		log.Panicln("ElasticSearch error!")
	}

	es_res := ElasticStopwordResponse{}
	err = json.Unmarshal(es_response.Bytes(), &es_res)
	if err != nil {
		log.Panic(err)
	}

	var buff bytes.Buffer
	seen := make(map[string]int)
	for _, token := range es_res.Tokens {
		if _, ok := seen[token.Token]; !ok {
			_, err = buff.WriteString(token.Token)
			_, err = buff.WriteString(" ")
			seen[token.Token] = 1
		}
	}
	if err != nil {
		log.Panic(err)
	}

	return strings.Trim(buff.String(), " ")
}

var textRe = regexp.MustCompile(`[^a-zA-Z0-9]+`)
var numRe = regexp.MustCompile(`[0-9]+`)

func cleanText(text string) string {
	return strings.ToLower(textRe.ReplaceAllString(text, " "))
}

func getNumbers(text string) string {
	nums := numRe.FindAllString(text, -1)
	var ret bytes.Buffer
	seen := make(map[string]int)
	for _, num := range nums {
		if _, ok := seen[num]; !ok {
			ret.WriteString(num)
			ret.WriteString(" ")
			seen[num] = 1
		}
	}

	return strings.Trim(ret.String(), " ")
}

func writeResToFile(f *os.File, results []Result, topic string, desc string) {
	var buff bytes.Buffer
	for _, res := range(results) {
		_, err := buff.WriteString(res.Topic)
		_, err = buff.WriteString(" 0 ")
		_, err = buff.WriteString(res.Id)
		_, err = buff.WriteString(" ")
		_, err = buff.WriteString(res.Rank)
		_, err = buff.WriteString(" ")
		_, err = buff.WriteString(res.Score)
		_, err = buff.WriteString(" ")
		_, err = buff.WriteString(desc)
		_, err = buff.WriteString("\n")
		if err != nil {
			log.Panic(err)
		}
	}
	_, err := f.Write(buff.Bytes())
	if err != nil {
		log.Panic(err)

	}
}

func getElasticResForQuery(text string, topic string, runName string, exclude string) []Result {
	body := map[string]interface{}{
		"_source" : []string{"id"},
		"from": 0,
		"size": NUM_RESULTS,
		"query" : map[string]interface{}{
			"match" : map[string]interface{}{
				"plain_text" : text,
			},
		},
	}
	return getElasticRes(body, topic, runName, exclude)
}

func getElasticRes(query map[string]interface{}, topic string, runName string, exclude string) []Result {

	ro := &grequests.RequestOptions{
		JSON: query,
	}
	es_response, err := grequests.Post("http://localhost:9200/ussc/_search", ro)
	if err != nil {
		log.Panicln(err)
	}

	if es_response.StatusCode != 200 {
		log.Panicln("ElasticSearch error!")
	}

	es_res := ElasticSearchResponse{}
	err = json.Unmarshal(es_response.Bytes(), &es_res)
	if err != nil {
		log.Panicln(err)
	}

	results := make([]Result, len(es_res.Hits.Hits))
	rank := 0
	rank_pos := -1
	for i := range es_res.Hits.Hits {
		if es_res.Hits.Hits[i].Id == exclude {
			rank_pos = i
			continue
		} else {
			results[i] = Result {
				Topic: string(topic),
				Id: es_res.Hits.Hits[i].Id,
				Rank: strconv.Itoa(rank),
				Score: fmt.Sprintf("%.6f", es_res.Hits.Hits[i].Score,),
				RunName: runName,
			}
			rank++
		}
	}

	if len(results) != 0 && rank_pos != -1 {
		results = append(results[:rank_pos], results[rank_pos+1:]...)
	}
	return results
}

func isNum(word string) bool {
	_, err := strconv.Atoi(word)
	if err == nil {
		return true
	} else {
		return false
	}
}

func loadTopics() map[string]Topic {
	topics := make(map[string]Topic)

	for topic := 1; topic < 101; topic++ {
		topic_string := strconv.Itoa(topic)

		var tf_name_buff bytes.Buffer
		tf_name_buff.WriteString(topic_path)
		tf_name_buff.WriteString(topic_string)
		tf_name_buff.WriteString(".json")

		var topicData Topic
		topic_file, err := ioutil.ReadFile(tf_name_buff.String())
		if err != nil {
			log.Panic(err)
		}
		if err := json.Unmarshal(topic_file, &topicData); err != nil {
			log.Panic(err)
		}
		topics[topic_string] = topicData
	}
	return topics
}

func createRunFile(run_name string, topics map[string]Topic) {
	var buff bytes.Buffer
	buff.WriteString(run_file_path)
	buff.WriteString(run_name)
	buff.WriteString(run_f_name)

	runFile := open(buff.String())

	for topic := 1; topic < 101; topic++ {
		topic_string := strconv.Itoa(topic)
		fmt.Println("Topic -", topic, "- runname -", run_name)

		var topic_case_id string
		skip_write := false

		topicData := topics[topic_string]
		topic_case_id = strconv.Itoa(topicData.CaseId)

		var res []Result

		if run_name == "toppar" {
			para := topicData.CitingParagraph
			for	_, extract := range topicData.CaseExtract {
				para = strings.Replace(para, extract, "", -1)
			}

			para = cleanText(para)
			numbers := getNumbers(para)
			para = removeStop(para)
			para = para + " " + numbers
			res = getElasticResForQuery(para, topic_string, run_name, topic_case_id)
		} else if run_name == "topsen" {
			sentence := topicData.CitingSentence
			for	_, extract := range topicData.CaseExtract {
				sentence = strings.Replace(sentence, extract, "", -1)
			}
			sentence = cleanText(sentence)
			numbers := getNumbers(sentence)
			sentence = removeStop(sentence)
			sentence = sentence + " " + numbers

			res = getElasticResForQuery(sentence, topic_string, run_name, topic_case_id)
		} else if run_name == "adhockey" {
			keyword_sen := ""
			for _, keyword := range topicData.RelevantKeywords {
				keyword_sen += keyword + " "
			}

			res = getElasticResForQuery(strings.Trim(keyword_sen, " "), topic_string, run_name, topic_case_id)
		} else {
			if strings.Contains(run_name, "adhocbool") {
				run_num, _ := strconv.Atoi(string(run_name[len(run_name) - 1]))
				run_num -= 1
				if run_num < len(topicData.EsQuery) {
					query := topicData.EsQuery[run_num]

					// exclude topic case from es results
					query["_source"] = []string{"id"}
					query["from"] = 0
					query["size"] = NUM_RESULTS
					res = getElasticRes(query, topic_string, run_name, topic_case_id)
				} else {
					skip_write = true
				}
			} else if strings.Contains(run_name, "adhocsim") {

				run_num, _ := strconv.Atoi(string(run_name[len(run_name) - 1]))
				run_num -= 1
				if run_num < len(topicData.Query) {

					qry := topicData.Query[run_num]
					qry = strings.Replace(qry, "AND", "", -1)
					qry = strings.Replace(qry, "OR", "", -1)
					qry = strings.Replace(qry, "(", "", -1)
					qry = strings.Replace(qry, ")", "", -1)
					qry = strings.Replace(qry, "\"", "", -1)
					res = getElasticResForQuery(qry, topic_string, run_name, topic_case_id)
				} else {
					skip_write = false
				}
			} else if strings.Contains(run_name, "plm") {
				run_num := 0
				smooth := 0
				var measure string

				end_pos := len(run_name)
				if unicode.IsDigit(rune(run_name[end_pos-2])) {
					smooth, _ = strconv.Atoi(run_name[end_pos-2:])
					if unicode.IsDigit(rune(run_name[end_pos-5])) {
						run_num, _ = strconv.Atoi(run_name[end_pos-5: end_pos-3])
						measure = run_name[:end_pos-5]
					} else {
						run_num, _ = strconv.Atoi(string(run_name[end_pos-4]))
						measure = run_name[:end_pos-4]
					}
				} else {
					smooth, _ = strconv.Atoi(string(run_name[end_pos-1]))
					if unicode.IsDigit(rune(run_name[end_pos-4])) {
						run_num, _ = strconv.Atoi(run_name[end_pos-4:end_pos-2])
						measure = run_name[:len(run_name)-4]
					} else {
						run_num, _ = strconv.Atoi(string(run_name[end_pos-3]))
						measure = run_name[:end_pos-3]
					}
				}
				run_num -= 1

				var p_f_name_buff bytes.Buffer
				p_f_name_buff.WriteString(auto_gen_methods_path)
				p_f_name_buff.WriteString(topic_string)
				p_f_name_buff.WriteString("_")
				p_f_name_buff.WriteString(measure)
				p_f_name_buff.WriteString("_")
				p_f_name_buff.WriteString(strconv.Itoa(smooth))
				p_f_name_buff.WriteString("_auto_query_terms.json")

				var proportions ProportionFile
				proportion_file, err := ioutil.ReadFile(p_f_name_buff.String())
				if err != nil {
					log.Panic(err)
				}
				err = json.Unmarshal(proportion_file, &proportions)

				var sentence bytes.Buffer
				for _, term := range proportions.Content.Query[run_num].Terms {
					sentence.WriteString(term)
					sentence.WriteString(" ")
				}
				res = getElasticResForQuery(sentence.String(), topic_string, run_name, topic_case_id)
			} else {
				run_num := 0
				measure := ""
				end_pos := len(run_name)
				if unicode.IsDigit(rune(run_name[end_pos-2])) {
					run_num, _ = strconv.Atoi(run_name[end_pos-2:])
					measure = run_name[:end_pos-2]
				} else {
					run_num, _ = strconv.Atoi(run_name[end_pos-1:])
					measure = run_name[:end_pos-1]
				}

				run_num -= 1

				var p_f_name_buff bytes.Buffer
				p_f_name_buff.WriteString(auto_gen_methods_path)
				p_f_name_buff.WriteString(topic_string)
				p_f_name_buff.WriteString("_")
				p_f_name_buff.WriteString(measure)
				p_f_name_buff.WriteString("_auto_query_terms.json")

				var proportions ProportionFile
				proportion_file, err := ioutil.ReadFile(p_f_name_buff.String())
				if err != nil {
					log.Panic(err)
				}
				err = json.Unmarshal(proportion_file, &proportions)

				var sentence bytes.Buffer
				for _, term := range proportions.Content.Query[run_num].Terms {
					sentence.WriteString(term)
					sentence.WriteString(" ")
				}
				res = getElasticResForQuery(sentence.String(), topic_string, run_name, topic_case_id)
			}

		}
		if !skip_write {
			writeResToFile(runFile, res, topic_string, run_name)
		}
	}
	runFile.Close()
}

func main() {
	start := time.Now()
	runs := []string{"adhocbool1", "adhocbool2", "adhocbool3", "adhocsim1", "adhocsim2", "adhocsim3", "adhockey", "topsen", "toppar"}
	base := []string{"idfs", "idfp", "plms", "plmp", "klis", "klip"}

	for _, run := range base {
		for i := 1; i < 12; i ++ {
			if strings.Contains(run, "plm") {
				for j := 1; j < 11; j++ {
					runs = append(runs, run + strconv.Itoa(i) + "_" + strconv.Itoa(j))
				}
			} else {
				runs = append(runs, run + strconv.Itoa(i))
			}
		}
	}

	maxGoroutines := 30
	guard := make(chan struct{}, maxGoroutines)

	topics := loadTopics()
	run_len := len(runs)

	var wg sync.WaitGroup
	wg.Add(run_len)

	for i := 0; i < run_len; i++ {
		guard <- struct{}{}
		go func(i int) {
			defer wg.Done()
			createRunFile(runs[i], topics)
			<-guard
		}(i)
	}
	wg.Wait()

	fmt.Println("Time taken -", time.Since(start))
}
