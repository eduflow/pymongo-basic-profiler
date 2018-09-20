import warnings

from bson import ObjectId
import pymongo
from pymongo_basic_profiler import OpTracker


warnings.filterwarnings('ignore', 'DeprecationWarning')


def test_insert():
    with OpTracker() as op_tracker:
        client = pymongo.MongoClient()
        db = client.test_optracker_db
        db.people.insert({'email': 'jane@example.org'})
        db.people.insert_one({'email': 'john@example.org'})
        # db.people.insert_many(
        #     [{'email': 'jane@example.org'}, {'email': 'john@example.org'}]
        # )
        db.people.save({'email': 'john@example.org'})
        assert len(op_tracker.inserts) == 3


def test_update():
    with OpTracker() as op_tracker:
        client = pymongo.MongoClient()
        db = client.test_optracker_db
        db.people.update_one(
            {'email': 'jane@example.org'}, {'$set': {'name': 'Jane N. Doe'}}
        )
        db.people.update(
            {'email': 'john@example.org'}, {'$set': {'name': 'John N. Doe'}}
        )
        db.people.replace_one(
            {'email': 'john@example.org'},
            {'name': 'John N. Doe', 'email': 'john@example.org'},
        )
        db.people.save({'_id': ObjectId(), 'email': 'john@example.org'})

        assert len(op_tracker.updates) == 4


def test_remove():
    with OpTracker() as op_tracker:
        client = pymongo.MongoClient()
        db = client.test_optracker_db
        db.people.delete_one({'email': 'jane@example.org'})
        db.people.delete_many({'email': {'$regex': 'example.org$'}})
        db.people.remove({'email': 'john@example.org'})

        assert len(op_tracker.removes) == 3


def test_find():
    with OpTracker() as op_tracker:
        client = pymongo.MongoClient()
        db = client.test_optracker_db
        db.people.find_one({'email': 'jane@example.org'})
        db.people.find_one({'email': 'john@example.org'})
        for person in db.people.find({'email': {'$regex': 'example.org$'}}):
            pass

        assert len(op_tracker.queries) == 3


def test_readme():
    with OpTracker() as op_tracker:
        client = pymongo.MongoClient()
        db = client.test_optracker_db
        db.people.insert({'name': 'Jane Doe', 'email': 'jane@example.org'})
        db.people.find_one({'email': 'jane@example.org'})
        db.people.find_one({'name': 'Jane Doe'})
        assert len(op_tracker.inserts) == 1
        assert len(op_tracker.queries) == 2
        res = op_tracker.queries[0]['result']
        del res[0]['_id']
        assert res == [{'name': 'Jane Doe', 'email': 'jane@example.org'}]
