from surprise import Dataset, NormalPredictor, Reader, accuracy, SVD, KNNBasic
from surprise.model_selection import cross_validate, KFold
import pandas as pd 

df = pd.read_csv("data/RatingsToTrainSample.csv")
#print(df.head())   # Shows first 5 rows
#print(df.columns)  # Shows column names

reader = Reader(rating_scale=(1, 10))

# The columns must correspond to user id, item id and ratings (in that order).
data = Dataset.load_from_df(df[["user_id", "movie_id", "rating"]], reader)

# We can now use this dataset as we please, e.g. calling cross_validate
cross_validate(NormalPredictor(), data, cv=2)


# define a cross-validation iterator
kf = KFold(n_splits=3)

algo = SVD()

for trainset, testset in kf.split(data):

    # train and test algorithm.
    algo.fit(trainset)
    predictions = algo.test(testset)

    # Compute and print Root Mean Squared Error
    accuracy.rmse(predictions, verbose=True)


