#!/usr/bin/env python
#
import argparse
import database
import random
import hashlib
import os
import numpy as np
import re
import operator
import tensorflow as tf
import math

def normalizeText(t):
    t = re.sub('<.>|<..>', ' ', t.lower())
    return re.sub('[^a-z0-9 ]', '', t)

def computeTFDataForProducts(products, vocab_indices, category_indices, seenCategories):
    xs = []
    ys = []
    for p in products:
        text = normalizeText(p['name'] + ' ' + p['description'])
        words = text.split()
        bow = np.zeros(len(vocab_indices))
        for w in words:
            if w in vocab_indices:
                bow[vocab_indices[w]] = 1
        y = np.zeros(len(seenCategories))
        y[category_indices[p['category_id']]] = 1
        xs.append(bow)
        ys.append(y)
    return xs, ys

def prepWordTraining(products):
    vocab = {}
    seenCategories = []
    for p in products:
        if p['category_id'] not in seenCategories:
            seenCategories.append(p['category_id'])
        text = normalizeText(p['name'] + ' ' + p['description'])
        words = text.split()
        for w in words:
            vocab[w] = 1 if w not in vocab else vocab[w]+1
    sorted_vocab = sorted(vocab.items(), key=operator.itemgetter(1))
    vocab_indices = dict((v,k) for k,v in enumerate([w[0] for w in sorted_vocab[-20000:]]))
    category_indices = dict((v,k) for k,v in enumerate(seenCategories))
    
    vocabSize = len(vocab_indices)
    numCategories = len(seenCategories)

    x = tf.placeholder(tf.float32, shape=[None, vocabSize], name='words_input')
    y_ = tf.placeholder(tf.float32, [None, numCategories], name='words_y_target')
    
    num_hidden_layers = 100
    
    stdv1 = 1.0 / math.sqrt(vocabSize)
    w1 = tf.Variable(tf.random_uniform([vocabSize, num_hidden_layers], minval=-stdv1, maxval=stdv1))
    b1  = tf.Variable(tf.random_uniform([num_hidden_layers], minval=-stdv1, maxval=stdv1))
    h1 = tf.nn.relu(tf.matmul(x, w1) + b1)
    
    stdv2 = 1.0 / math.sqrt(num_hidden_layers)
    w2 = tf.Variable(tf.random_uniform([num_hidden_layers, numCategories], minval=-stdv2, maxval=stdv2))
    b2  = tf.Variable(tf.random_uniform([numCategories], minval=-stdv2, maxval=stdv2))

    y_logits = tf.matmul(h1, w2) + b2
    y = tf.nn.softmax(y_logits)
    
    cross_entropy = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(y_logits, y_))
    train_step = tf.train.AdamOptimizer().minimize(cross_entropy)

    correct_prediction = tf.equal(tf.argmax(y, 1), tf.argmax(y_, 1))
    prediction = tf.argmax(y, 1)
    
    return x, y, h1, y_logits, y_, train_step, prediction, vocab_indices, category_indices, seenCategories
    
def classifyText(categories):
    if len(categories) <= 10:    
        name = ",".join(categories)
    else:
        name = ",".join(categories[0:5]) + ("... (%d total)" % + len(categories))
    experimentId = db.addExperiment("Text classification of: %s" % name)

    products = db.getProducts(categories)
    random.shuffle(products)

    x, y, h1, y_logits, y_, train_step, prediction, vocab_indices, category_indices, seenCategories = prepWordTraining(products)
    
    sess = tf.InteractiveSession()
    tf.global_variables_initializer().run()

    train = products[:(int(.9*len(products)))]
    test = products[len(train):]

    test_x, test_y = computeTFDataForProducts(test, vocab_indices, category_indices, seenCategories)

    # Train

    for _ in range(5):
        random.shuffle(train)

        print("eval (N=%d)" % len(test_x))
        correct = 0
        for i, t in enumerate(test_x):
            guess = sess.run(prediction, feed_dict={x:np.reshape(t, [1, len(t)])})
            if guess[0] == np.argmax(test_y[i]):
                correct += 1
        print("Calculated accuracy: %f" % (float(correct)/len(test_x)))

        print "train"
        for i in xrange(0, len(train), 32):
            batch_xs, batch_ys = computeTFDataForProducts(train[i:(i+32)], vocab_indices, category_indices, seenCategories)
          
            sess.run(train_step, feed_dict={x: batch_xs, y_: batch_ys})
            if i % 100 == 0:
                print "batch offset %d of %d" % (i, len(train))

    # Record experiment results
    correct = 0
    for i, p in enumerate(test):
        guess = sess.run(y, feed_dict={x:np.reshape(test_x[i], [1, len(test_x[i])])})
        guess = np.squeeze(guess)
        predictedCat = seenCategories[np.argmax(guess)]
        if p['category_id'] == predictedCat:
            correct += 1
        db.addPredictedCategory(experimentId, p['id'], predictedCat, np.max(guess))
    print("Calculated accuracy: %f" % (float(correct)/len(test)))

def dumpTextCorpus():
    products = db.getProducts()
    for p in products:
        print "%s %s" % (normalizeText(p['name']), normalizeText(p['description']))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default='crawl.db', help="Path to sqlite db file")
    parser.add_argument("--images-path", default='images', help="Path to directory in which images should be saved")
    parser.add_argument("--categories", help="categories to predict.  If not specified, all categories with 1000 products are trained")
    args = parser.parse_args()

    global db
    db = database.Database(args.db_path)

    categories = []
    if args.categories:
        categories = args.categories.split(',')
        
    classifyText(categories)

if __name__ == "__main__":
    main()
