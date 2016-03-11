import nltk
from nltk.probability import ELEProbDist
import nltk.classify.util
from nltk.classify import NaiveBayesClassifier
import re
import os

pos_content = []

neg_content = []

neut_content = []

fh = open('training_data.csv', 'r')

count = 0
print 'Gathering Content...'
for i, ln in enumerate(fh.readlines()):
    count += 1
    if count % 10000 == 0:
        print str(count) + " Lines"
    cat = ln.split(',')[0][1:-1]
    tweet = re.compile(r"@(\w+)").sub('', ln.split(',')[5]).strip()[1:-1]
    if cat == "0":
        neg_content.append((tweet, 'negative'))
    elif cat == "4":
        pos_content.append((tweet, 'positive'))
    elif cat == "2":
        neut_content.append((tweet, 'neutral'))

content = []

tweets = neg_content + pos_content

count = 0
print 'Filtering Content...'
for words, sentiment in tweets:
    count += 1

    if count % 10000 == 0:
        print str(count) + "/" + str(len(tweets))
    words_filtered = [e.lower() for e in words.split() if len(e) >= 3]
    content.append((words_filtered, sentiment))


def get_words_in_content(content):
    all_words = []
    for (words, sentiment) in content:
        all_words.extend(words)
    return all_words


def get_word_features(wordlist):
    wordlist = nltk.FreqDist(wordlist)
    word_features = wordlist.keys()
    return word_features


def extract_features(document):
    document_words = set(document)
    features = {}
    for word in word_features:
        features['contains(%s)' % word] = (word in document_words)
    return features


print 'Gathering word features...'
word_features = get_word_features(get_words_in_content(content))

tweet = "Jeansy went to the shop today and bought some milk"

training_set = nltk.classify.apply_features(extract_features, content)

print 'Training classifier...'
classifier = nltk.NaiveBayesClassifier.train(training_set)

print classifier.classify(extract_features(tweet.split()))