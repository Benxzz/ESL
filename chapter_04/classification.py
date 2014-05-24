__author__ = 'jrx'

import collections

import numpy as np
import pandas as pd

import common.base as base


def indicator_matrix(values):
    """ Transform a series of classes into a 0-1 classification matrix """
    # Take all the classes from y
    classes = sorted(set(values))

    y = pd.DataFrame()

    # Transform classes into a classification matrix
    for cls in classes:
        y[cls] = values == cls

    return y.astype(int)


def classification_error_rate(classifier, coords, values):
    """ Calculate classification error rate """
    yhat = classifier.classify(coords)
    return (yhat != values).mean()


class LeastSquaresClassifier(base.Classification):
    """ Train linear least squares classifier """

    def __init__(self, coords, values):
        super(LeastSquaresClassifier, self).__init__()

        self.classes = sorted(set(values))

        value_indicator_matrix = indicator_matrix(values)
        inverse_cov = np.linalg.inv(np.dot(coords.T, coords))

        self.betahat = pd.DataFrame(
            np.dot(np.dot(inverse_cov, coords.T), value_indicator_matrix),
            columns=self.classes, index=coords.columns
        )

    def classify(self, samples):
        """ Classify x """
        yhat = samples.dot(self.betahat)
        return yhat.apply(lambda x: x.idxmax(), axis=1)


class LinearDiscriminantClassifier(base.Classification):
    """ Train linear discriminant classifier """

    def __init__(self, coords, values):
        super(LinearDiscriminantClassifier, self).__init__()

        self.classes = sorted(set(values))

        k = len(self.classes)

        n, p = coords.shape

        # Per-class probabilities
        self.probabilities = pd.Series(collections.Counter(values), index=self.classes) / values.size

        # Calculate means
        x2 = coords.copy()
        x2['y'] = values
        self.means = x2.groupby('y').apply(lambda v: v.mean()).drop('y', 1)

        self.sigma = np.zeros([p, p])

        for idx, x in x2.iterrows():
            mu = self.means.loc[x.y]
            xv = x.drop('y') - mu
            self.sigma += np.outer(xv, xv)

        self.sigma /= (n - k)
        self.sigma_inv = np.linalg.inv(self.sigma)

        # The second part of this expression calculates mu^T Sigma mu per each class
        self.constants = np.log(self.probabilities) - 0.5 * (self.means * np.dot(self.sigma_inv, self.means.T).T).sum(1)

        self.discrimination_matrix = np.dot(self.sigma_inv, self.means.values.T)

    def classify(self, samples):
        """ Classify X """
        df = pd.DataFrame(np.dot(samples, self.discrimination_matrix), columns=self.classes)
        return (df + self.constants).apply(lambda row: row.idxmax(), axis=1)


class QuadraticDiscriminantClassifier(base.Classification):
    """ Train quadratic discriminant classifier """

    def __init__(self, coords, values):
        super(QuadraticDiscriminantClassifier, self).__init__()

        self.classes = sorted(set(values))

        # Per-class probabilities
        self.probabilities = pd.Series(collections.Counter(values), index=self.classes) / values.size

        # Calculate means
        x2 = coords.copy()
        x2['y'] = values
        self.means = x2.groupby('y').apply(lambda v: v.mean()).drop('y', 1)

        self.covariance = {}
        self.covariance_inv = {}
        self.covariance_det = {}

        for cls in self.classes:
            selected = x2[x2['y'] == cls]
            mu = self.means.loc[cls]

            cov = np.cov(selected.drop('y', 1) - mu, rowvar=0, ddof=1)

            self.covariance[cls] = cov
            self.covariance_inv[cls] = np.linalg.inv(cov)
            self.covariance_det[cls] = np.linalg.det(cov)

        # Constant part of the discrimination function
        self.constants = np.log(self.probabilities) - 0.5 * np.log(pd.Series(self.covariance_det, index=self.classes))

    def classify(self, samples):
        """ Classify X """

        columns = {}

        for cls in self.classes:
            const = self.constants[cls]
            mu = self.means.loc[cls]
            xs = samples - mu
            sigma_inv = self.covariance_inv[cls]
            columns[cls] = const - 0.5 * (xs * np.dot(sigma_inv, xs.T).T).sum(1)

        discriminant_matrix = pd.concat(columns, axis=1)
        return discriminant_matrix.apply(lambda row: row.idxmax(), axis=1)
