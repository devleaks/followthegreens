# Graph (vertices and edges) manipulation class.
# Vertex and Edge definition customized for our need.
# Dijkstra stolen at https://www.bogotobogo.com/python/python_graph_data_structures.php
# AStar implemented by myself.
#
import os
import math
import json
from functools import reduce

from .geo import (
    Point,
    Line,
    Polygon,
    bearing,
    distance,
    nearestPointToLines,
    destination,
    pointInPolygon,
    turn,
)
from .globals import (
    logger,
    MOVEMENT,
    TAXIWAY_WIDTH_CODE,
    TAXIWAY_TYPE,
    TAXIWAY_ACTIVE,
    TAXIWAY_DIRECTION,
)


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
        # note: cannot add opposite neighbor.add_neighbor(self) since might be one way only

    def get_connections(self, graph, options={}):
        return self.adjacent.keys()

    def get_neighbors(self):
        return list(map(lambda a: (a, self.adjacent[a]), self.adjacent))

    def turn(self, src, dst) -> float | None:
        # Turn angle coming from src and going to dst
        # Will be used as a weighted extra cost when visited from src to dst
        if src.id not in self.adjacent and self.id not in src.adjacent:
            logger.warning(
                f"turn: at {self.id}: from {src.id} to {dst.id}, src not in adjacents {self.adjacent} or self not in src {src.adjacent} ({type(self.id)})"
            )
        if dst.id not in self.adjacent and self.id not in dst.adjacent:
            logger.warning(
                f"turn: at {self.id}: from {src.id} to {dst.id}, dst not in adjacents {self.adjacent} or self not in dst {dst.adjacent} ({type(self.id)})"
            )
        b1 = bearing(src, self)
        b2 = bearing(self, dst)
        return turn(b1, b2)


class Active:
    def __init__(self, active, runways):
        self.active = TAXIWAY_ACTIVE(active)
        self.runways = runways.split(",")
        if len(self.runways) > 4:
            logger.warning("more than 4 runways for active segment")

    def __str__(self):
        return self.active + ":" + ",".join(self.runways)


class Edge(Line):
    def __init__(self, src, dst, cost, direction, usage, name):
        Line.__init__(self, src, dst)
        self.name = name  # segment name, not unique! For documentation only.
        self.cost = cost  # cost = distance to next vertext

        # oneway/twoway
        self.direction = TAXIWAY_DIRECTION(direction)

        # taxiway/runway, width code
        self.usage = TAXIWAY_TYPE.RUNWAY
        self.width_code = None
        if usage.startswith("taxiway"):
            self.usage = TAXIWAY_TYPE.TAXIWAY
            if len(usage) == 9:
                self.width_code = TAXIWAY_WIDTH_CODE(usage[8].upper())

        # inner/outer (non formal guess)
        self.usage2 = TAXIWAY_DIRECTION.BOTH  # default, unused
        if "inn" in name.lower():
            self.usage2 = TAXIWAY_DIRECTION.INNER
        elif "out" in name.lower():
            self.usage2 = TAXIWAY_DIRECTION.OUTER

        self.active = []  # array of segment activity, activity can be departure, arrival, or ils.
        # departure require clearance. plane cannot stop on segment of type ils.

    def props(self):
        props = self.properties
        props["stroke"] = "#000080"  # “taxiway”, “runway”, runway dark blue
        props["stroke-width"] = 5
        props["stroke-opacity"] = 1
        if self.usage[0:4] == "taxi":
            props["stroke-width"] = 3
            props["stroke"] = "#f0f080"  # yellowish

            if self.has_active(TAXIWAY_ACTIVE.ARRIVAL):
                props["stroke"] = "#00f000"  # green
            if self.has_active(TAXIWAY_ACTIVE.DEPARTURE):
                props["stroke"] = "#0000F0"  # blue
            if self.has_active(TAXIWAY_ACTIVE.ILS):
                props["stroke"] = "#ff0000"  # red

        if self.direction == TAXIWAY_DIRECTION.ONEWAY:
            props["stroke"] = "#00dd00"
            props["stroke-width"] = 1
            props["stroke-style"] = "dashed"

        # Meta
        props["name"] = self.name
        props["cost"] = self.cost
        props["direction"] = self.direction.value
        props["usage"] = self.usage.value  # “taxiway”, “runway”
        props["usage2"] = self.usage2.value  # inner, “outer”, "both"
        props["width_code"] = self.width_code.value if self.width_code is not None else "-"
        props["active"] = self.showActives()
        props["active-rwy"] = self.mkActives()
        return props

    @property
    def is_inner(self):
        return self.usage2 != TAXIWAY_DIRECTION.OUTER

    @property
    def is_inner_only(self):
        return self.usage2 == TAXIWAY_DIRECTION.INNER

    @property
    def is_outer(self):
        # note:   !is_inner <> is_outer
        return self.usage2 != TAXIWAY_DIRECTION.INNER

    @property
    def is_outer_only(self):
        return self.usage2 == TAXIWAY_DIRECTION.OUTER

    def add_active(self, active, runways):
        return self.active.append(Active(active, runways))

    def has_active(self, active: TAXIWAY_ACTIVE | None = None):
        if active is not None:
            for a in self.active:
                if a.active == active:
                    return True
            return False
        return self.has_active(TAXIWAY_ACTIVE.DEPARTURE) or self.has_active(TAXIWAY_ACTIVE.ARRIVAL)

    def mkActives(self):
        ret = []
        for a in self.active:
            ret.append({a.active.value: ",".join(a.runways)})  # "ils": "12L,30R"
        return ret

    def showActives(self) -> str:
        ret = ""
        if self.has_active(TAXIWAY_ACTIVE.ARRIVAL):
            ret = ret + "/A"
        if self.has_active(TAXIWAY_ACTIVE.DEPARTURE):
            ret = ret + "/D"
        if self.has_active(TAXIWAY_ACTIVE.ILS):
            ret = ret + "/I"
        return ret.strip("/")


class Graph:  # Graph(FeatureCollection)?
    def __init__(self, name: str = "unamed"):
        self.name = name
        self.vert_dict = {}
        self.edges_arr = []

        # Try to guess if information is supplied or not
        self._uses_width_code = False
        self._oneways = False
        self._runways = False

    def __str__(self):
        return json.dumps({"type": "FeatureCollection", "features": self.features()})

    def __iter__(self):
        return iter(self.vert_dict.values())

    def stats(self):
        logger.debug(f"graph {self.name}")
        s = {}
        ad = {}
        for k, v in self.vert_dict.items():
            if v.usage not in s:
                s[v.usage] = 0
            s[v.usage] = s[v.usage] + 1
            la = len(v.adjacent)
            if la not in ad:
                ad[la] = 0
            ad[la] = ad[la] + 1
        logger.debug(f"{len(self.vert_dict)} vertices: {s}, {ad}")

        s = {}
        mi = 100000
        ma = 0
        s["width_code"] = 0
        for v in self.edges_arr:
            if v.direction not in s:
                s[v.direction] = 0
            s[v.direction] = s[v.direction] + 1
            if v.width_code is not None:
                s["width_code"] += 1
                if v.width_code not in s:
                    s[v.width_code] = 0
                s[v.width_code] = s[v.width_code] + 1
            if v.usage not in s:
                s[v.usage] = 0
            s[v.usage] = s[v.usage] + 1
            if v.usage2 not in s:
                s[v.usage2] = 0
            s[v.usage2] = s[v.usage2] + 1
            if "active" not in s:
                s["active"] = 0
            if v.has_active():
                s["active"] = s["active"] + 1
            mi = min(mi, v.cost)
            ma = max(ma, v.cost)
        logger.debug(f"{len(self.edges_arr)} edges: {s}, cost=[{round(mi, 2)}, {round(ma, 2)}]")
        if logger.level < 10:
            fn = os.path.join(os.path.dirname(__file__), "..", f"ftg_tn_{self.name}.geojson")
            with open(fn, "w") as fp:
                print(self, file=fp)
            logger.debug(f"taxiway network saved in {fn}")

    def features(self):
        def add(arr, v):
            arr.append(v.feature())
            return arr

        return reduce(add, self.edges_arr, [])

    def add_vertex(self, node, point, usage, name=""):
        new_vertex = Vertex(node, point, usage, name="")
        self.vert_dict[node] = new_vertex
        return new_vertex

    def get_vertex(self, n):
        return self.vert_dict.get(n)

    # Options taxiwayOnly = True|False, minSizeCode = {A,B,C,D,E,F}
    def get_connections(self, src, options={}):
        if len(options) > 0:
            connectionKeys = []
            for dst in src.adjacent.keys():
                v = self.get_edge(src.id, dst)
                code = v.width_code
                if code is None:
                    code = TAXIWAY_WIDTH_CODE.F
                txyOk = ("taxiwayOnly" in options and options["taxiwayOnly"] and v.usage != TAXIWAY_TYPE.RUNWAY) or ("taxiwayOnly" not in options)
                scdOk = ("minSizeCode" in options and options["minSizeCode"] <= code) or ("minSizeCode" not in options)
                # logger.debug("%s %s %s %s %s" % (dst, v.usage, code, txyOk, scdOk))
                if txyOk and scdOk:
                    connectionKeys.append(dst)

            return connectionKeys

        return src.adjacent.keys()

    def add_edge(self, edge):
        if edge.start.id in self.vert_dict and edge.end.id in self.vert_dict:
            self.edges_arr.append(edge)
            self.vert_dict[edge.start.id].add_neighbor(self.vert_dict[edge.end.id].id, edge.cost)

            if edge.direction == TAXIWAY_DIRECTION.TWOWAY:
                self.vert_dict[edge.end.id].add_neighbor(self.vert_dict[edge.start.id].id, edge.cost)
            # Check if information is available
            if edge.width_code is not None:
                self._uses_width_code = True
            if edge.direction == TAXIWAY_DIRECTION.ONEWAY:
                self._oneways = True
            if edge.usage == TAXIWAY_TYPE.RUNWAY:
                self._runways = True
        else:
            logger.critical(f"vertex not found when adding edges {edge.src},{edge.dst}")

    def clone(
        self,
        width_code: str,
        move: str,
        respect_width: bool = False,
        respect_inner: bool = False,
        use_runway: bool = True,
        respect_oneway: bool = True,
    ):
        width_strict = False
        # logger.debug(
        #     f"cloning.. width_code={width_code} (strict={width_strict}), move={move} "
        #     + f"respect_width={respect_width} respect_inner={respect_inner} use_runway={use_runway} respect_oneway={respect_oneway}"
        # )

        candidates = []
        for e in self.edges_arr:
            # Exclusions
            if respect_width:
                if e.width_code is not None:
                    if width_code.value > e.width_code.value:  # not wide enough
                        continue
                elif width_strict:
                    logger.debug(f"strict width mode: edge {e} has no width code, ignored")
                    continue  # no width info on taxiway, use strict width mode, so must ignore this unlabelled segment

            if respect_inner:
                if move == MOVEMENT.ARRIVAL and e.is_outer:  # arrival cannot use outer rwy
                    continue
                if move == MOVEMENT.DEPARTURE and e.is_inner:  # departure cannot use inner rwy
                    continue
            if not use_runway and e.usage == TAXIWAY_TYPE.RUNWAY:  # cannot use runway for taxiing
                # Note: My understanding of 1202 runway is that runway indicates that the edge IS a runway and can be used for taxiing
                #       Clearance should be obtained first from ATC. Of course.
                continue

            # if not excluded, add it
            if not respect_oneway and e.direction == TAXIWAY_DIRECTION.ONEWAY:
                e.direction = TAXIWAY_DIRECTION.TWOWAY
            candidates.append(e)

        graph = Graph(f"{self.name} cloned with restrictions ({move},{width_code},{respect_width},{respect_inner},{use_runway},{respect_oneway})")
        for e in candidates:
            start = graph.add_vertex(e.start.id, Point(e.start.lat, e.start.lon), e.start.usage, e.start.name)
            end = graph.add_vertex(e.end.id, Point(e.end.lat, e.end.lon), e.end.usage, e.end.name)

        for e in candidates:
            start = graph.get_vertex(e.start.id)
            end = graph.get_vertex(e.end.id)
            t = e.usage.value
            if e.width_code is not None:
                t = t + "_" + e.width_code.value
            graph.add_edge(Edge(start, end, e.cost, e.direction.value, t, e.name))

        logger.debug(
            f"cloned {len(graph.edges_arr)}/{len(self.edges_arr)}: width_code={width_code} (strict={width_strict}), move={move} "
            + f"respect_width={respect_width} respect_inner={respect_inner} use_runway={use_runway} respect_oneway={respect_oneway}"
        )
        return graph

    def get_edge(self, src, dst):
        arr = list(filter(lambda x: x.start.id == src and x.end.id == dst, self.edges_arr))
        if len(arr) > 0:
            return arr[0]

        arr = list(
            filter(
                lambda x: x.start.id == dst and x.end.id == src and x.direction == TAXIWAY_DIRECTION.TWOWAY,
                self.edges_arr,
            )
        )
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
            code = edge.width_code
            if code is None:
                code = TAXIWAY_WIDTH_CODE.F
            txyOk = ("taxiwayOnly" in options and options["taxiwayOnly"] and edge.usage != TAXIWAY_TYPE.RUNWAY) or ("taxiwayOnly" not in options)
            scdOk = ("minSizeCode" in options and options["minSizeCode"] <= code) or ("minSizeCode" not in options)
            # logger.debug("%s %s %s %s %s" % (dst, v.usage, code, txyOk, scdOk))
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
            if len(v.adjacent) > 0:  # It must be a vertex connected to the network of taxiways
                d = distance(v, point)
                if d < shortest:
                    shortest = d
                    closest = n
        logger.debug(f"{closest} at {round(shortest, 1)}m")
        return [closest, shortest]

    def findVertexInPolygon(self, polygon):
        vertices = []
        for n, v in self.vert_dict.items():
            if pointInPolygon(v, polygon):
                vertices.append(v)
        return vertices

    def findClosestVertexAheadGuess(self, point, brng, speed):
        MAX_AHEAD = 500  # m, we could make algorithm grow these until vertex found "ahead"
        MAX_LATERAL = 200  # m
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
        logger.debug(f"found at ahead={ahead}, lateral={lateral}")
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
        logger.debug(f"{ahead}, {lateral}, inside {len(vertices)}.")

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
            logger.warning("source or target missing")
            return route

        # These are all the nodes which have not been visited yet
        unvisited_nodes = list(self.get_vertices())
        # logger.debug("Unvisited nodes", unvisited_nodes)
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
        while unvisited_nodes:
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
                    # min_node as current_node
                    min_node = current_node

            # Iterating through the connected nodes of current_node (for
            # example, a is connected with b and c having values 10 and 3
            # respectively) and the weight of the edges
            connected = self.get_connections(self.get_vertex(min_node), options)
            # logger.debug("connected %s %s", min_node, connected)
            for child_node in connected:
                e = self.get_edge(min_node, child_node)  # should always be found...
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
        # logger.debug("predecessor %s", predecessor)
        while node and node != source and len(predecessor.keys()) > 0:
            # As it is not necessary that the target node can be reached from # the source node, we must enclose it in a try block
            route.insert(0, node)
            if node in predecessor:
                node = predecessor[node]
            else:
                node = False

        if not node:
            logger.warning(f"Dijkstra: could not find route from {source} to {target}")
            return None
        else:
            # Including the source in the path
            route.insert(0, source)
            logger.debug(f"route: {'-'.join([str(r) for r in route])}")
            return route

    def heuristic(self, a, b):  # On demand
        """
        Heuristic function is straight distance (to goal)
        """
        va = self.get_vertex(a)
        if va is None:
            logger.warning(f"invalid vertex id a={a}")
            return math.inf
        vb = self.get_vertex(b)
        if vb is None:
            logger.warning(f"invalid vertex id b={b}")
            return math.inf
        return distance(va, vb)

    def get_neighbors(self, a):
        """
        Returns a vertex's neighbors with weight to reach.
        """
        v = self.get_vertex(a)
        if v is None:
            logger.warning(f"vertex not found: {a}")
            return []
        return v.get_neighbors()

    def AStar(self, start_node, stop_node):
        # open_list is a list of nodes which have been visited, but who's neighbors
        # haven't all been inspected, starts off with the start node
        # closed_list is a list of nodes which have been visited
        # and who's neighbors have been inspected
        #
        # Stolen here: https://stackabuse.com/basic-ai-concepts-a-search-algorithm/
        # Heuristics adjusted for geography (direct distance to target, necessarily smaller or equal to goal)
        #
        # Returns list of vertices (path) or None
        #
        open_list = set([start_node])
        closed_list = set([])

        # g contains current distances from start_node to all other nodes
        # the default value (if it's not found in the map) is +infinity
        g = {}

        g[start_node] = 0

        # parents contains an adjacency map of all nodes
        parents = {}
        parents[start_node] = start_node

        while len(open_list) > 0:
            n = None

            # find a node with the lowest value of f() - evaluation function
            for v in open_list:
                if n is None or g[v] + self.heuristic(v, stop_node) < g[n] + self.heuristic(n, stop_node):
                    n = v

            if n is None:
                logger.warning("AStar: route not found")
                return None

            # if the current node is the stop_node
            # then we begin reconstructin the path from it to the start_node
            if n == stop_node:
                reconst_path = []
                while parents[n] != n:
                    reconst_path.append(n)
                    n = parents[n]
                reconst_path.append(start_node)
                reconst_path.reverse()

                return reconst_path

            # for all neighbors of the current node do
            for m, weight in self.get_neighbors(n):
                # if the current node isn't in both open_list and closed_list
                # add it to open_list and note n as it's parent
                if m not in open_list and m not in closed_list:
                    open_list.add(m)
                    parents[m] = n
                    g[m] = g[n] + weight

                # otherwise, check if it's quicker to first visit n, then m
                # and if it is, update parent data and g data
                # and if the node was in the closed_list, move it to open_list
                else:
                    if g[m] > g[n] + weight:
                        g[m] = g[n] + weight
                        parents[m] = n

                        if m in closed_list:
                            closed_list.remove(m)
                            open_list.add(m)

            # remove n from the open_list, and add it to closed_list
            # because all of his neighbors were inspected
            open_list.remove(n)
            closed_list.add(n)

        logger.warning("AStar: route not found")
        return None
