from copy import deepcopy
import functools
import time
import inspect
import os

import pymongo
import pymongo.collection
import pymongo.cursor


_original_methods = {
    'insert': pymongo.collection.Collection._insert,
    'update': pymongo.collection.Collection._update,
    'remove': pymongo.collection.Collection._delete,
    'refresh': pymongo.cursor.Cursor._refresh,
}


class OpTracker(object):
    def __init__(self, with_stacktraces=False):
        self.with_stacktraces = with_stacktraces

        self.queries = []
        self.inserts = []
        self.updates = []
        self.removes = []

        self._method_insert = self._build_insert()
        self._method_update = self._build_update()
        self._method_remove = self._build_remove()
        self._method_refresh = self._build_refresh()

    def install_tracker(self):
        if pymongo.collection.Collection._insert != self._method_insert:
            pymongo.collection.Collection._insert = self._method_insert
        if pymongo.collection.Collection._update != self._method_update:
            pymongo.collection.Collection._update = self._method_update
        if pymongo.collection.Collection._delete != self._method_remove:
            pymongo.collection.Collection._delete = self._method_remove
        if pymongo.cursor.Cursor._refresh != self._method_refresh:
            pymongo.cursor.Cursor._refresh = self._method_refresh

    def uninstall_tracker(self):
        if pymongo.collection.Collection._insert == self._method_insert:
            pymongo.collection.Collection._insert = _original_methods['insert']
        if pymongo.collection.Collection._update == self._method_update:
            pymongo.collection.Collection._update = _original_methods['update']
        if pymongo.collection.Collection._delete == self._method_remove:
            pymongo.collection.Collection._delete = _original_methods['remove']
        # if pymongo.collection.Collection.save == self._save:
        #     pymongo.collection.Collection.save = _original_methods['save']
        if pymongo.cursor.Cursor._refresh == self._method_refresh:
            pymongo.cursor.Cursor._refresh = _original_methods['refresh']

    def reset(self):
        self.queries = []
        self.inserts = []
        self.updates = []
        self.removes = []

    def __enter__(self):
        self.install_tracker()
        return self

    def __exit__(self, *args):
        self.uninstall_tracker()

    def _build_insert(self):
        @functools.wraps(_original_methods['insert'])
        def _insert(
            collection_self,
            docs,
            ordered=True,
            check_keys=True,
            manipulate=False,
            write_concern=None,
            op_id=None,
            bypass_doc_val=False,
            session=None,
        ):
            start_time = time.time()
            result = _original_methods['insert'](
                collection_self,
                docs,
                ordered=True,
                check_keys=True,
                manipulate=False,
                write_concern=None,
                op_id=None,
                bypass_doc_val=False,
                session=None,
            )
            total_time = (time.time() - start_time) * 1000

            __traceback_hide__ = True
            self.inserts.append(
                {
                    'document': docs,
                    'time': total_time,
                    'stack_trace': self._get_stacktrace(),
                }
            )
            return result

        return _insert

    def _build_update(self):
        @functools.wraps(_original_methods['update'])
        def _update(
            collection_self,
            sock_info,
            criteria,
            document,
            upsert=False,
            manipulate=False,
            multi=False,
            **kwargs
        ):
            start_time = time.time()
            result = _original_methods['update'](
                collection_self,
                sock_info,
                criteria,
                document,
                upsert=upsert,
                multi=multi,
                **kwargs
            )
            total_time = (time.time() - start_time) * 1000

            __traceback_hide__ = True
            self.updates.append(
                {
                    'document': document,
                    'upsert': upsert,
                    'multi': multi,
                    'criteria': criteria,
                    'time': total_time,
                    'stack_trace': self._get_stacktrace(),
                }
            )
            return result

        return _update

    def _build_remove(self):
        @functools.wraps(_original_methods['remove'])
        def _delete(
            collection_self,
            sock_info,
            criteria,
            multi,
            write_concern=None,
            op_id=None,
            ordered=True,
            collation=None,
            session=None,
            retryable_write=False,
        ):
            start_time = time.time()
            result = _original_methods['remove'](
                collection_self,
                sock_info,
                criteria,
                multi,
                write_concern=write_concern,
                op_id=op_id,
                ordered=ordered,
                collation=collation,
                session=session,
                retryable_write=retryable_write,
            )
            total_time = (time.time() - start_time) * 1000

            __traceback_hide__ = True
            self.removes.append(
                {
                    'criteria': criteria,
                    'time': total_time,
                    'stack_trace': self._get_stacktrace(),
                }
            )
            return result

        return _delete

    def _build_refresh(self):
        @functools.wraps(_original_methods['refresh'])
        def _cursor_refresh(cursor_self):
            # Look up __ private instance variables
            def privar(name):
                return getattr(cursor_self, '_Cursor__{0}'.format(name))

            if privar('id') is not None:
                # getMore not query - move on
                return _original_methods['refresh'](cursor_self)

            # NOTE: See pymongo/cursor.py+557 [_refresh()] and
            # pymongo/message.py for where information is stored

            # Time the actual query
            start_time = time.time()
            result = _original_methods['refresh'](cursor_self)
            total_time = (time.time() - start_time) * 1000

            query_son = privar('query_spec')()

            __traceback_hide__ = True
            query_data = {
                'time': total_time,
                'operation': 'find',
                'stack_trace': self._get_stacktrace(),
            }

            # Collection in format <db_name>.<collection_name>
            collection_name = privar('collection')
            query_data['collection'] = collection_name.full_name.split('.')[1]

            query_result = list(deepcopy(privar('data')))

            if query_data['collection'] == '$cmd':
                # The query can be embedded within $query in some cases
                query_son = query_son.get("$query", query_son)

                query_data['operation'] = 'command'
                # Handle count as a special case
                if 'count' in query_son:
                    # Information is in a different format to a standar query
                    query_data['collection'] = query_son['count']
                    query_data['operation'] = 'count'
                    query_data['skip'] = query_son.get('skip')
                    query_data['limit'] = abs(query_son.get('limit', 0))
                    query_data['result'] = query_result
                    query_data['query'] = query_son['query']
                elif 'aggregate' in query_son:
                    query_data['collection'] = query_son['aggregate']
                    query_data['operation'] = 'aggregate'
                    query_data['query'] = query_son['pipeline']
                    query_data['skip'] = 0
                    query_data['result'] = query_result
                    query_data['limit'] = None
            else:
                # Normal Query
                query_data['skip'] = privar('skip')
                query_data['limit'] = abs(privar('limit') or 0)
                query_data['query'] = query_son.get('$query') or query_son
                query_data['result'] = query_result
                query_data['ordering'] = self._get_ordering(query_son)

            self.queries.append(query_data)

            return result

        return _cursor_refresh

    def _get_ordering(self, son):
        """Helper function to extract formatted ordering from dict.
        """

        def fmt(field, direction):
            return '{0}{1}'.format({-1: '-', 1: '+'}[direction], field)

        if '$orderby' in son:
            return ', '.join(fmt(f, d) for f, d in son['$orderby'].items())

    def _get_stacktrace(self):
        if self.with_stacktraces:
            try:
                stack = inspect.stack()
            except IndexError:
                # this is a work around because python's inspect.stack() sometimes fail
                # when jinja templates are on the stack
                return [
                    (
                        "",
                        0,
                        "Error retrieving stack",
                        "Could not retrieve stack. IndexError exception occured in inspect.stack(). "
                        "This error might occur when jinja2 templates is on the stack.",
                    )
                ]

            return self._tidy_stacktrace(reversed(stack))
        else:
            return []

    # Taken from Django Debug Toolbar 0.8.6
    def _tidy_stacktrace(self, stack):
        """
        Clean up stacktrace and remove all entries that:
        1. Are the last entry (which is part of our stacktracing code)
        ``stack`` should be a list of frame tuples from ``inspect.stack()``
        """
        pymongo_path = os.path.realpath(os.path.dirname(pymongo.__file__))

        trace = []
        for frame, path, line_no, func_name, text in (f[:5] for f in stack):
            s_path = os.path.realpath(path)
            # Support hiding of frames -- used in various utilities that provide
            # inspection.
            if '__traceback_hide__' in frame.f_locals:
                continue
            if pymongo_path in s_path:
                continue
            if not text:
                text = ''
            else:
                text = (''.join(text)).strip()
            trace.append((path, line_no, func_name, text))
        return trace
