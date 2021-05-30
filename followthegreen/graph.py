# Graph (vertices and edges) manipulation class.
# Vertex and Edge definition customized for our need.
# Dijkstra stolen at https://www.bogotobogo.com/python/python_graph_data_structures.php
#
import logging
import math
import json
from functools import reduce
from .geo import Point, Line, Polygon, distance, nearestPointToLines, destination, pointInPolygon
from .globals import TAXIWAY_DIR_TWOWAY, DEPARTURE, ARRIVAL


class Vertex(Point):  ## Vertex(Point)

    def __init__(self, node, point, usage, name=""):
        Point.__init__(self, point.lat, point.lon)
        self.id = node
        self.usage = usage
        self.name = name
        self.adjacent = {}
        self.setProp("vid", node)  # vertex id


    def props(self):
        self.setProp("marker-color", "#888888")  # “dest”, “init”, “both” or “junc”
        if self.usage == "dest":
            self.setProp("marker-color", "#00aa00")
        elif self.usage == "init":
            self.setProp("marker-color", "#aa0000")
        elif self.usage == "both":
            self.setProp("marker-color", "#0000aa")

        self.setProp("id", self.id)
        self.setProp("use", self.usage)
        self.setProp("name", self.name)
        self.setProp("marker-size", "small")
        return self.properties


    def add_neighbor(self, neighbor, weight=0):
        self.adjacent[neighbor] = weight


    def get_connections(self, graph, options = {}):
        return self.adjacent.keys()


class Active:

    def __init__(self, active, runways):
        self.active = active
        self.runways = runways.split(",")

    def __str__(self):
        return self.active + ":" + ",".join(self.runways)


class Edge(Line):

    def __init__(self, src, dst, cost, direction, usage, name):
        Line.__init__(self, src, dst)
        self.cost = cost    # cost = distance to next vertext
        self.direction = direction  # direction of vertex: oneway or twoway
        self.usage = usage  # type of vertex: runway or taxiway or taxiway_X where X is width code (A-F)
        self.name = name    # segment name, not unique!
        self.active = []    # array of segment activity, activity can be departure, arrival, or ils.
        # departure require clearance. plane cannot stop on segment of type ils.

    def props(self):
        props = self.properties
        props["stroke"] = "#aa0000"  # “taxiway”, “runway”
        props["stroke-width"] = 1
        props["stroke-opacity"] = 1
        if self.usage[0:4] == "taxi":
            props["stroke"] = "#aaaa00"

        if self.direction == "oneway":
            props["stroke"] = "#00dd00"
            props["stroke-width"] = 2

        props["name"] = self.name
        props["cost"] = self.cost
        props["direction"] = self.direction
        props["usage"] = self.usage
        props["active"] = self.mkActives()
        return props

    def mkActives(self):
        ret = []
        for a in self.active:
            ret.append({
                a.active: ",".join(a.runways)  # "ils": "12L,30R"
            })
        return ret

    def add_active(self, active, runways):
        return self.active.append(Active(active, runways))

    def has_active(self, active=None):
        if active:
            for a in self.active:
                if a.active == active:
                    return True
            return False
        return self.has_active(DEPARTURE) or self.has_active(ARRIVAL)

    def widthCode(self, default=None):
        if self.usage and len(self.usage) == 9:
            return self.usage[8]
        return default

class Graph:  # Graph(FeatureCollection)?

    def __init__(self):
        self.vert_dict = {}
        self.edges_arr = []


    def __str__(self):
        return json.dumps({
            "type": "FeatureCollection",
            "features": self.features()
        })


    def __iter__(self):
        return iter(self.vert_dict.values())


    def features(self):
        def add(arr, v):
            arr.append(v.feature(self))
            return arr
        return reduce(add, self.edges_arr, [])


    def add_vertex(self, node, point, usage, name = ""):
        new_vertex = Vertex(node, point, usage, name = "")
        self.vert_dict[node] = new_vertex
        return new_vertex


    def get_vertex(self, n):
        if n in self.vert_dict:
            return self.vert_dict[n]
        else:
            return None


    # Options taxiwayOnly = True|False, minSizeCode = {A,B,C,D,E,F}
    def get_connections(self, src, options={}):
        if len(options) > 0:
            connectionKeys = []
            for dst in src.adjacent.keys():
                v = self.get_edge(src.id, dst)
                code = v.widthCode("F")
                txyOk = ("taxiwayOnly" in options and options["taxiwayOnly"] and v.usage != "runway") or ("taxiwayOnly" not in options)
                scdOk = ("minSizeCode" in options and options["minSizeCode"] <= code) or ("minSizeCode" not in options)
                # logging.debug("%s %s %s %s %s" % (dst, v.usage, code, txyOk, scdOk))
                if txyOk and scdOk:
                    connectionKeys.append(dst)

            return connectionKeys

        return src.adjacent.keys()


    def add_edge(self, edge):
        if edge.start.id in self.vert_dict and edge.end.id in self.vert_dict:
            self.edges_arr.append(edge)
            self.vert_dict[edge.start.id].add_neighbor(self.vert_dict[edge.end.id].id, edge.cost)

            if(edge.direction == TAXIWAY_DIR_TWOWAY):
                self.vert_dict[edge.end.id].add_neighbor(self.vert_dict[edge.start.id].id, edge.cost)
        else:
            logging.critical("Graph::add_edge: vertex not found when adding edges %s,%s", edge.src, edge.dst)


    def get_edge(self, src, dst):
        arr = list(filter(lambda x: x.start.id == src and x.end.id == dst, self.edges_arr))
        if len(arr) > 0:
            return arr[0]

        arr = list(filter(lambda x: x.start.id == dst and x.end.id == src and x.direction == TAXIWAY_DIR_TWOWAY, self.edges_arr))
        if len(arr) > 0:
            return arr[0]

        return None


    def get_vertices(self):
        return self.vert_dict.keys()


    def get_connected_vertices(self, options={}):
        # List of vertices may contain unconnected vertices.
        # Same options as get_connections
        connected = []

        for edge in self.edges_arr:
            code = edge.widthCode("F")  # default all ok.
            txyOk = ("taxiwayOnly" in options and options["taxiwayOnly"] and edge.usage != "runway") or ("taxiwayOnly" not in options)
            scdOk = ("minSizeCode" in options and options["minSizeCode"] <= code) or ("minSizeCode" not in options)
            # logging.debug("%s %s %s %s %s" % (dst, v.usage, code, txyOk, scdOk))
            if txyOk and scdOk:
                if edge.src not in connected:
                    connected.append(edge.src)
                if edge.dst not in connected:
                    connected.append(edge.dst)

        return connected


    def findClosestPointOnEdges(self, point):  # @todo: construct array of lines on "add_edge"
        return nearestPointToLines(point, self.edges_arr)


    def findClosestVertex(self, point):
        closest = None
        shortest = math.inf
        for n, v in self.vert_dict.items():
            if len(v.adjacent) > 0:    # It must be a vertex connected to the network of taxiways
                d = distance(v, point)
                if d < shortest:
                    shortest = d
                    closest = n
        logging.debug("Graph::findClosestVertex: %s at %f", closest, shortest)
        return [closest, shortest]


    def findVertexInPolygon(self, polygon):
        vertices = []
        for n, v in self.vert_dict.items():
            if pointInPolygon(v, polygon):
                vertices.append(v)
        return vertices



    def findClosestVertexAheadGuess(self, point, brng, speed):
        MAX_AHEAD = 500     # m, we could make algorithm grow these until vertex found "ahead"
        MAX_LATERAL = 200   # m
        AHEAD_START = 300
        LATERAL_START = 40
        AHEAD_INC = 100
        LATERAL_INC = 20
        found = [None]
        ahead = AHEAD_START
        lateral = LATERAL_START

        while not found[0] and ahead < MAX_AHEAD:
            while not found[0] and lateral < MAX_LATERAL:
                found = self.findClosestVertexAhead(point, brng, speed, ahead, lateral)
                lateral += LATERAL_INC
            ahead += AHEAD_INC
            lateral = LATERAL_START
        logging.debug("Graph::findClosestVertexAheadGuess: found at ahead=%d, lateral=%d.", ahead, lateral)
        return found


    def findClosestVertexAhead(self, point, brng, speed, ahead=200, lateral=100):
        # We draw a triangle in front of the plane, plane is at apex, base is AHEAD meters in front (bearing)
        # and LATERAL meters wide left and right.
        # Should set maxahead from speed, if fast, maxahead large.
        MAX_AHEAD = 200  # m
        maxpoint = destination(point, brng, MAX_AHEAD)
        base = destination(point, brng, ahead)
        baseL = destination(base, brng + 90, lateral)
        baseR = destination(base, brng - 90, lateral)
        triangle = Polygon([point, baseL, baseR])
        vertices = self.findVertexInPolygon(triangle)
        logging.debug("Graph::findClosestVertexAhead: %d, %d, inside %s.", ahead, lateral, len(vertices))

        v = None
        d = math.inf
        if len(vertices) > 0:
            for vertex in vertices:
                dist = math.inf
                if ahead > MAX_AHEAD:
                    dist = distance(maxpoint, vertex)  # uses base rather than point ;-)
                else:
                    dist = distance(base, vertex)  # uses base rather than point ;-)
                if dist < d:
                    d = dist
                    v = vertex
        if v:
            return [v.id, d]
        return [None, d]


    def Dijkstra(self, source, target, options={}):
        # This will store the Shortest path between source and target node
        route = []
        if not source or not target:
            logging.debug("Graph::Dijkstra: source or target missing")
            return route

        # These are all the nodes which have not been visited yet
        unvisited_nodes = list(self.get_vertices())
        # logging.debug("Unvisited nodes", unvisited_nodes)
        # It will store the shortest distance from one node to another
        shortest_distance = {}
        # It will store the predecessors of the nodes
        predecessor = {}

        # Iterating through all the unvisited nodes
        for nodes in unvisited_nodes:
            # Setting the shortest_distance of all the nodes as infinty
            shortest_distance[nodes] = math.inf

        # The distance of a point to itself is 0.
        shortest_distance[str(source)] = 0

        # Running the loop while all the nodes have been visited
        while(unvisited_nodes):
            # setting the value of min_node as None
            min_node = None
            # iterating through all the unvisited node
            for current_node in unvisited_nodes:
                # For the very first time that loop runs this will be called
                if min_node is None:
                    # Setting the value of min_node as the current node
                    min_node = current_node
                elif shortest_distance[min_node] > shortest_distance[current_node]:
                    # I the value of min_node is less than that of current_node, set
                    #min_node as current_node
                    min_node = current_node

            # Iterating through the connected nodes of current_node (for
            # example, a is connected with b and c having values 10 and 3
            # respectively) and the weight of the edges
            connected = self.get_connections(self.get_vertex(min_node), options)
            # logging.debug("connected %s %s", min_node, connected)
            for child_node in connected:
                e = self.get_edge(min_node, child_node) # should always be found...
                cost = e.cost

                # checking if the value of the current_node + value of the edge
                # that connects this neighbor node with current_node
                # is lesser than the value that distance between current nodes
                # and its connections
                #
                if (cost + shortest_distance[min_node]) < shortest_distance[child_node]:
                    # If true  set the new value as the minimum distance of that connection
                    shortest_distance[child_node] = cost + shortest_distance[min_node]
                    # Adding the current node as the predecessor of the child node
                    predecessor[child_node] = min_node

            # After the node has been visited (also known as relaxed) remove it from unvisited node
            unvisited_nodes.remove(min_node)

        # Till now the shortest distance between the source node and target node
        # has been found. Set the current node as the target node
        node = target
        # Starting from the goal node, we will go back to the source node and
        # see what path we followed to get the smallest distance
        # logging.debug("predecessor %s", predecessor)
        while node and node != source and len(predecessor.keys()) > 0:
            # As it is not necessary that the target node can be reached from # the source node, we must enclose it in a try block
            route.insert(0,node)
            if node in predecessor:
                node = predecessor[node]
            else:
                node = False

        if not node:
            logging.debug("could not find route from %s to %s", source, target)
            return None
        else:
            # Including the source in the path
            route.insert(0, source)
            logging.debug("route: %s", "-".join(route))
            return route
