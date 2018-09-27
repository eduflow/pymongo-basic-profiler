import warnings

from bson import ObjectId
import pymongo
from pymongo_basic_profiler import OpTracker
import pytest


warnings.filterwarnings('ignore', 'DeprecationWarning')


@pytest.fixture
def db():
    client = pymongo.MongoClient()
    yield client.test_optracker_db


@pytest.fixture(autouse=True)
def _clean_db(db):
    '''Cleans the collection after use'''
    db.people.delete_many({})
    assert db.people.count() == 0
    yield


def test_insert(db):
    with OpTracker() as op_tracker:
        db.people.insert({'email': 'jane@example.org'})
        db.people.insert_one({'email': 'john@example.org'})
        db.people.save({'name': 'John Doe', 'email': 'johndoe@example.org'})
        assert len(op_tracker.inserts) == 3
        assert (
            db.people.find_one({'email': 'johndoe@example.org'})['name'] == 'John Doe'
        )

    # Assert that we we no longer count inserts
    db.people.insert({'email': 'jane2@example.org'})
    db.people.save({'email': 'john2@example.org'})
    assert len(op_tracker.inserts) == 3

    # - and that inserts work as expected
    assert db.people.find({'email': 'john2@example.org'}).count() == 1
    assert db.people.find({'email': 'jane2@example.org'}).count() == 1


def test_bulk_write(db):
    ops = [
        pymongo.UpdateOne(
            {'email': 'jane1@example.org'}, {'$set': {'name': 'Jane1'}}, upsert=True
        ),
        pymongo.UpdateOne(
            {'email': 'jane2@example.org'}, {'$set': {'name': 'Jane2'}}, upsert=True
        ),
        pymongo.UpdateOne(
            {'email': 'john@example.org'}, {'$set': {'name': 'John1'}}, upsert=True
        ),
        pymongo.UpdateOne(
            {'email': 'john@example.org'}, {'$set': {'name': 'John2'}}, upsert=True
        ),
    ]

    with OpTracker() as op_tracker:
        db.people.bulk_write(ops)
        assert len(op_tracker.bulk_writes) == 1
        assert db.people.find_one({'email': 'jane1@example.org'})['name'] == 'Jane1'

    # Assert that we we no longer count bulk_writes
    db.people.bulk_write(ops)
    assert len(op_tracker.bulk_writes) == 1

    # - and that bulk_writes work as expected
    assert db.people.find_one({'email': 'jane1@example.org'})['name'] == 'Jane1'


def test_update(db):
    user_id = ObjectId()

    with OpTracker() as op_tracker:
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
        db.people.save({'_id': user_id, 'email': 'john@example.org'})

        assert len(op_tracker.updates) == 4

    # Assert that we can still update -- after having used the `OpTracker`
    db.people.update_one({'_id': user_id}, {'$set': {'email': 'john2@example.org'}})
    assert db.people.find_one({'_id': user_id})['email'] == 'john2@example.org'
    assert len(op_tracker.updates) == 4


def test_remove(db):
    db.people.insert_many(
        [{'email': 'jane@example.org'}, {'email': 'john@example.org'}]
    )
    assert db.people.count() == 2

    with OpTracker() as op_tracker:
        db.people.delete_one({'email': 'jane@example.org'})
        db.people.delete_many({'email': {'$regex': 'example.org$'}})
        db.people.remove({'email': 'john@example.org'})

        assert len(op_tracker.removes) == 3

    assert db.people.count() == 0


def test_find(db):
    with OpTracker() as op_tracker:
        db.people.find_one({'email': 'jane@example.org'})
        db.people.find_one({'email': 'john@example.org'})
        for person in db.people.find({'email': {'$regex': 'example.org$'}}):
            pass

        assert len(op_tracker.queries) == 3


def test_readme(db):
    with OpTracker() as op_tracker:
        db.people.insert({'name': 'Jane Doe', 'email': 'jane@example.org'})
        db.people.find_one({'email': 'jane@example.org'})
        db.people.find_one({'name': 'Jane Doe'})
        assert len(op_tracker.inserts) == 1
        assert len(op_tracker.queries) == 2
        res = op_tracker.queries[0]['result']
        del res[0]['_id']
        assert res == [{'name': 'Jane Doe', 'email': 'jane@example.org'}]
