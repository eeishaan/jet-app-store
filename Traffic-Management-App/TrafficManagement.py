#!/usr/bin/env python

import sys, os, re, glob, datetime, time
from jnpr.jet.JetHandler import *
import smtplib
import grpc
import rib_service_pb2 as Route
import authentication_service_pb2
import prpd_common_pb2
# sender = 'JET-Router-R1@juniper.net'
# receivers = ['gvenkata@juniper.net']

R1 = '10.221.132.89'
R1_IFL_SNMP_INDEX = '511'
DIP = '1.1.1.1/32'
NIP = '10.1.1.2'
APP_USER = 'regress'
APP_PASSWORD = 'MaRtInI'

DEFAULT_ROUTE_NEXTHOP_IP = NIP
DEFAULT_ROUTE_PREFERENCE_LIST = [5,15]
DEFAULT_ROUTE_METRIC_LIST = [3,5]
DEFAULT_ROUTE_APP_ID = '111:222'
DEFAULT_ROUTE_FAMILY_TYPE = FamilyType.af_unspec
DEFAULT_ROUTE_NEXTHOP_TYPE = None
DEFAULT_ROUTE_PREFIX_AND_LENGTH = '1.1.1.1/32'
DEFAULT_ROUTE_GET_APP_ID = '0'
DEFAULT_ROUTE_GET_TABLE_NAME = 'inet6.0'
DEFAULT_ROUTE_GET_PREFIX = '1.1.1.1'

channel = grpc.insecure_channel(R1+':32767')
sec_stub = authentication_service_pb2.LoginStub(channel)
cred = authentication_service_pb2.LoginRequest(user_name=APP_USER,password=APP_PASSWORD,client_id='1211114')
res = sec_stub.LoginCheck(cred)
print "Authentication "+('success' if res else 'failure')
route_stub = Route.RibStub(channel)

def on_message(message):
    print("----------------------------------------EVENT RECEIVED-------------------------------------------")
    print "Event Type : " + message['jet-event']['event-id']

    if 'attributes' in message['jet-event'].keys():
        print "Event Attributes : ", message['jet-event']['attributes']['message']
    else:
        print "Attributes : NULL"
    print("-------------------------------------------------------------------------------------------------")

    p1 = re.search(r"Event " + re.escape(R1_IFL_SNMP_INDEX) + r" triggered by Alarm 1, (\w+) threshold",
                   str(message['jet-event']['attributes']))
    res = p1.group(1)
    route_present = None
    if (res == "rising") and (route_present != True):
        print ("\n>>>>>>>>>>>>>>Primary Path input traffic rate is above threshold value<<<<<<<<<<<<<<<<<<<")

        # Add route as IFL input rate is above threshold
        # nexthop_list = []
        # n_list = NexthopInfo(nexthop_address=GatewayAddress(nexthop_ip=DEFAULT_ROUTE_NEXTHOP_IP))
        # nexthop_list.append(n_list)
        # preference = DEFAULT_ROUTE_PREFERENCE_LIST
        # metric = DEFAULT_ROUTE_METRIC_LIST

        # result = R1_route_handle.RouteAdd(RouteConfig(
        #                                        DEFAULT_ROUTE_APP_ID,
        #                                        DEFAULT_ROUTE_FAMILY_TYPE,
        #                                        DEFAULT_ROUTE_PREFIX_AND_LENGTH,
		# 			                           DEFAULT_ROUTE_NEXTHOP_TYPE,
        #                                        nexthop_list,
        #                                        None,None,preference,metric,0,None))
        
        netaddr = prpd_common_pb2.NetworkAddress(inet=jnx_addr_pb2.IpAddress(addr_string=DEFAULT_ROUTE_GET_PREFIX))
        rttablename = prpd_common_pb2.RouteTableName(name=DEFAULT_ROUTE_GET_TABLE_NAME)
        routeTable = prpd_common_pb2.RouteTable(rtt_name=rttablename)
        routematchFields = Route.RouteMatchFields(dest_prefix=netaddr,dest_prefix_len=32,table=routeTable)

        routeAddr = prpd_common_pb2.NetworkAddress(inet=jnx_addr_pb2.IpAddress(addr_string=DEFAULT_ROUTE_NEXTHOP_IP))
        gateway_list = Route.RouteGateway(gateway_address=routeAddr)
        nexthop_list = Route.RouteNexthop(gateways=gateway_list)

        route_entry = Route.RouteEntry(key=routematchFields, nexthop=nexthop_list)
        route_request = Route.RouteUpdateRequest(routes = route_entry)
        result = route_stub.RouteAdd(route_request)

        if result.status is Route.RouteOperStatus:
            route_present = True
            print "Added static route directly into control plane"
            print "Traffic to destination subnets routed via Secondary path"
            print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
            print '\n#############################Verifying RIB#######################################'
            result = R1_route_handle.RouteGet(DEFAULT_ROUTE_GET_APP_ID, DEFAULT_ROUTE_GET_TABLE_NAME, DEFAULT_ROUTE_GET_PREFIX)

            netaddr = prpd_common_pb2.NetworkAddress(inet=jnx_addr_pb2.IpAddress(addr_string="128.221.130.97"))
            rttablename = prpd_common_pb2.RouteTableName(name=DEFAULT_ROUTE_GET_TABLE_NAME)
            routeTable = prpd_common_pb2.RouteTable(rtt_name=rttablename)
            routematchFields = Route.RouteMatchFields(dest_prefix=netaddr,dest_prefix_len=0,table=routeTable)
            rrequest = Route.RouteGetRequest(key=routematchFields)
            result = route_stub.RouteGet(rrequest)
            print result
            for routes in result.routes:
                for hops in routes.nexthop:
                    print 'Next Hop Ips are:',hops.gateways.gateway_address.inet.addr_string
                    if hops.gateways.gateway_address.inet.addr_string == NIP:
                        print "Route add API injected route successfully"
            print '##################################################################################'
            # mail (message = """Subject: JET Notification:Traffic rate is above threshold on primary path.
            # Body: JET App rerouted traffic via secondary path""")
        else:
            print "V4RouteAdd service API activation failed \n"
            route_present = False
    elif (res == "falling") and (route_present != False):
        print ("\n>>>>>>>>>>>>>>Primary Path input traffic rate is below threshold value<<<<<<<<<<<<<<<<<<<")
        exit()
        # Delete route as IFL input rate is below threshold
        preference = DEFAULT_ROUTE_PREFERENCE_LIST
        metric = DEFAULT_ROUTE_METRIC_LIST
        result = R1_route_handle.RouteDelete(RouteConfig(
                                                      DEFAULT_ROUTE_APP_ID,
                                                      DEFAULT_ROUTE_FAMILY_TYPE,
                                                      DEFAULT_ROUTE_PREFIX_AND_LENGTH,
						                              DEFAULT_ROUTE_NEXTHOP_TYPE,
                                                      None,
                                                      None, None,preference,metric,0, None))
        print result
        if result.err_code is 0:
            route_present = False
            print "Primary path input traffic rate is below threshold, since deleted route"
            print "Entire Traffic routed back via Primary path"
            print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
            mail (message = """Subject: SMTP e-mail test
            JET App deleted route in R1""")
        else:
            print "V4RouteDelete service API deactivation failed \n"
            route_present = True
    else:
        print "No changes required \n"

def mail(message):
    smtpObj = smtplib.SMTP('smtp.juniper.net')
    smtpObj.sendmail(sender, receivers, message)
    print "Successfully sent email"

try:
    # Create a client handler for connecting to server
    client = JetHandler()

    # Open session with Thrift Servers
    client.OpenRequestResponseSession(device=R1, connect_timeout=300000, user=APP_USER, password=APP_PASSWORD, client_id= "1211111")
    print "\nEstablished connection with the", R1

    # Create a service handlers
    R1_route_handle = client.GetRouteService()
    R1_mgmt_handle = client.GetManagementService()

    # Create a event handlers to MQTT server
    evHandle = client.OpenNotificationSession(device=R1)

    # Subscribe for syslog events
    syslog = evHandle.CreateSyslogTopic("SNMPD_RMON_EVENTLOG")
    print "Subscribing to Syslog RMON notifications"
    evHandle.Subscribe(syslog, on_message)

    while 1:
        1 + 1

except Exception as tx:
    print '%s' % tx.message