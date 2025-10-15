import grpc
import distance_unary_pb2_grpc as pb2_grpc
import distance_unary_pb2 as pb2
from google.protobuf.json_format import MessageToJson
import json

if __name__ == "__main__":
    with grpc.insecure_channel("localhost:50051") as channel:
        stub = pb2_grpc.DistanceServiceStub(channel)

        # a SourceDest contains two Position: source and destination
        message = pb2.SourceDest(
            source=pb2.Position(
                latitude=-33.0351516, longitude=-70.5955963
            ),
            destination=pb2.Position(
                latitude=-33.0348327, longitude=-71.5980458
            ),
            unit="km"
        )

        print(f"Message sent:\n{MessageToJson(message)}\n")

        # call remote method
        response = stub.geodesic_distance(message)

        try:
            print("-----Response-----")
            print("Distance:", json.loads(MessageToJson(response))["distance"])
            print("Method:", json.loads(MessageToJson(response))["method"])
            print("Distance unit:", json.loads(MessageToJson(response))["unit"])
        except KeyError:
            print("One or more key are missing!")
