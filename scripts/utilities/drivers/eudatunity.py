# !/usr/bin/env python

import sys
import json
import urllib2
import base64
from pprint import pformat


class EudatRemoteSource:

    def _debugMsg(self, method, msg):
        """Internal: Print a debug message if debug is enabled.

        """
        if self.debug:
            print "[", method, "]", msg

    def __init__(self, conf, parent_logger=None):
        """initialize the object"""

        if parent_logger:
            self.logger = parent_logger
        else:
            self.logger = logging.getLogger('eudat')

        self.main_project = 'EUDAT'

        confkeys = ['host', 'username', 'password', 'carootdn', 'ns_prefix']
        missingp = []
        for key in confkeys:
            if not key in conf: missingp.append(key)
        if len(missingp) > 0:
            self.logger.warning('missing parameters: ' + pformat(missingp))
        self.conf = conf

        self.remote_users_list = self.getRemoteUsers()
#        print(pformat(remote_users_list))


    def queryUnity(self, sublink):
        """
        :param argument: url to unitydb with entity (entityID) or group (groupName)
        :return:
        """
        auth = base64.encodestring('%s:%s' % (self.conf['username'], self.conf['password']))[:-1]
        header = "Basic %s" % auth
        url = self.conf['host'] + sublink
        request = urllib2.Request(url)
        request.add_header("Authorization", header)
        try:
            response = urllib2.urlopen(request)
        except IOError:
            print "Wrong username or password"
            sys.exit(1)

        assert response.code == 200
        json_data = response.read()
        response_dict = json.loads(json_data)

        return response_dict

    def getRemoteUsers(self):
        """
        Get the remote users' list
        """

        self.logger.info("Getting list of users from eudat db...")
        # get list of all groups in Unity
        group_list = self.queryUnity("group/%2F")

        final_list = {}
        list_member = []
        users_map = {}
        attribs_map = {}
        for member_id in group_list['members']:
            user_record = self.queryUnity("entity/"+str(member_id))
            attr_list = {}
            for identity in user_record['identities']:
                if identity['typeId'] == "userName":
                    list_member.append(identity['value'])
                    users_map[member_id] = identity['value']
                elif identity['typeId'] == "persistent":
                    # Here we build the DN: the way to build it could change
                    # in the future.
                    userDN = '/CN=' + users_map[member_id] + '/CN=' \
                             + identity['value'] + self.conf['carootdn']
                    attr_list['DN'] = [userDN]
            attribs_map[users_map[member_id]] = attr_list

        final_list['members'] = list_member
        final_list['attributes'] = attribs_map

        # Query and get list of all user from Groups in Unity
        list_group = {}
        for group_name in group_list['subGroups']:
            member_list = self.queryUnity("group"+group_name)
            user_list = []
            for member_id in member_list['members']:
                user_list.append(users_map[member_id])
            list_group[group_name[1:]] = user_list

        final_list['groups'] = list_group

        return final_list

    def synchronize_user_db(self, data):
        """
        Synchronize the remote users' list with a local json file (user db)
        """

        for org,members in self.remote_users_list['groups'].iteritems():

            self.logger.info('Adding users belonging to ' + org + ' ...')
            org = self.conf['ns_prefix'] + org
            data[self.main_project]["groups"][org] = []
            for member in members:
                member = self.conf['ns_prefix'] + member
                data[self.main_project]["groups"][org].append(member)
                self.logger.debug('\tadded user %s' % (member,))

        return data


    def synchronize_user_attributes(self, data):
        """
        Synchronize the remote users' attributes with a local json file
        for the time beeing just the DNs are considered
        """
       
        for user,attrs in self.remote_users_list['attributes'].iteritems():

            self.logger.info('Adding DNs belonging to the user ' + user + ' ...')
            user = self.conf['ns_prefix'] + user
            data[user] = attrs['DN']
            self.logger.debug('\tadded user ' + user + '\' DNs: ' 
                              + pformat(attrs['DN']))

        return data
