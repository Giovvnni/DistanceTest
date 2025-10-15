import unittest
from geo_location import Position
import grpc
import distance_unary_pb2_grpc as pb2_grpc
import distance_unary_pb2 as pb2


# ----------------------------------------------------------------------
# 1. PRUEBAS DE VALIDACIÓN DE COORDENADAS (expected exceptions)
# ----------------------------------------------------------------------
class TestPositionValidation(unittest.TestCase):
    """
    En esta parte se prueban los límites de latitud y longitud definidos por el enunciado.
    Cada test verifica que se lance ValueError si la posición se sale del rango permitido.
    """

    def test_positive_latitude(self):
        """Prueba que una latitud mayor a 90° genere ValueError."""
        with self.assertRaises(ValueError):
            Position(91.0, 0.0, 0.0)

    def test_negative_latitude(self):
        """Prueba que una latitud menor a -90° también genere ValueError."""
        with self.assertRaises(ValueError):
            Position(-91.0, 0.0, 0.0)

    def test_positive_longitude(self):
        """Prueba que una longitud mayor a 180° lance ValueError."""
        with self.assertRaises(ValueError):
            Position(0.0, 181.0, 0.0)

    def test_negative_longitude(self):
        """Prueba que una longitud menor a -180° lance ValueError."""
        with self.assertRaises(ValueError):
            Position(0.0, -181.0, 0.0)


# ----------------------------------------------------------------------
# 2. PRUEBAS SOBRE EL SERVICIO gRPC (success paths y error handling)
# ----------------------------------------------------------------------
class TestDistanceService(unittest.TestCase):
    """
    Esta clase contiene pruebas que interactúan directamente con el servicio gRPC.
    Se validan tanto los casos correctos como los escenarios donde el servicio debería fallar.
    """

    def setUp(self):
        """Antes de cada test se abre el canal de comunicación y se prepara el stub del servicio."""
        self.channel = grpc.insecure_channel("localhost:50051")
        self.stub = pb2_grpc.DistanceServiceStub(self.channel)

    def tearDown(self):
        """Después de cada test se cierra el canal para evitar conexiones abiertas."""
        self.channel.close()

    def test_default_unit_should_match_km(self):
        """
        Si la unidad llega vacía (unit=""), el resultado debería ser casi igual
        a usar unit="km". Si difieren demasiado, el servicio estaría usando otra unidad por defecto.
        """
        msg_default = pb2.SourceDest(
            source=pb2.Position(latitude=-33.0351516, longitude=-70.5955963),
            destination=pb2.Position(latitude=-33.0348327, longitude=-71.5980458),
            unit=""
        )
        msg_km = pb2.SourceDest(
            source=pb2.Position(latitude=-33.0351516, longitude=-70.5955963),
            destination=pb2.Position(latitude=-33.0348327, longitude=-71.5980458),
            unit="km"
        )

        # Se hacen ambas llamadas y se comparan los resultados
        resp_default = self.stub.geodesic_distance(msg_default)
        resp_km = self.stub.geodesic_distance(msg_km)

        diff = abs(resp_default.distance - resp_km.distance)
        print(f"\n[DEBUG] Unidad vacía = {resp_default.distance:.3f} km, explícita = {resp_km.distance:.3f}, diff = {diff:.3f}")

        # Si la diferencia supera 1 km, se considera comportamiento incorrecto
        self.assertLess(
            diff, 1.0,
            msg="La unidad por defecto no coincide con kilómetros (usa .nautical() por error)."
        )

    def test_invalid_position_returns_invalid_response(self):
        """
        Cuando una posición tiene coordenadas fuera del rango válido,
        el servicio debería responder con distancia = -1.0 y unidad = 'invalid'.
        """
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=-95.0, longitude=-182.0),
            destination=pb2.Position(latitude=-33.035, longitude=-71.598),
            unit="km"
        )

        response = self.stub.geodesic_distance(msg)
        self.assertEqual(response.unit, "invalid")
        self.assertEqual(response.distance, -1.0)

    def test_unit_nautical_miles_conversion(self):
        """
        Se comprueba que al pedir unit='nm', la distancia sea coherente con la conversión desde km.
        (1 milla náutica ≈ 1.852 km)
        """
        msg_km = pb2.SourceDest(
            source=pb2.Position(latitude=-33.035, longitude=-70.596),
            destination=pb2.Position(latitude=-33.034, longitude=-71.598),
            unit="km"
        )
        msg_nm = pb2.SourceDest(
            source=pb2.Position(latitude=-33.035, longitude=-70.596),
            destination=pb2.Position(latitude=-33.034, longitude=-71.598),
            unit="nm"
        )

        resp_km = self.stub.geodesic_distance(msg_km)
        resp_nm = self.stub.geodesic_distance(msg_nm)

        # Se calcula la distancia esperada en millas náuticas usando la conversión aproximada
        expected_nm = resp_km.distance / 1.852
        self.assertAlmostEqual(resp_nm.distance, expected_nm, delta=0.5)
        self.assertEqual(resp_nm.unit, "nm")

    def test_valid_positions_km_distance(self):
        """
        Caso base: usando coordenadas válidas y unit='km' el servicio
        debería devolver una distancia positiva en kilómetros.
        """
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=-33.045, longitude=-71.619),
            destination=pb2.Position(latitude=-33.046, longitude=-71.629),
            unit="km"
        )
        response = self.stub.geodesic_distance(msg)
        self.assertGreater(response.distance, 0.0)
        self.assertEqual(response.unit, "km")

    def test_invalid_unit_crashes_server(self):
        """
        Se intenta provocar el fallo conocido del servidor enviando una unidad no reconocida ('m').
        Este caso debería lanzar un RpcError con código INTERNAL, demostrando el bug real.
        """
        msg = pb2.SourceDest(
            source=pb2.Position(latitude=-33.0351516, longitude=-70.5955963),
            destination=pb2.Position(latitude=-33.0348327, longitude=-71.5980458),
            unit="m"  # unidad inválida, el servidor no la maneja
        )

        with self.assertRaises(grpc.RpcError) as ctx:
            self.stub.geodesic_distance(msg)

        # Verificamos que el error sea interno del servidor (bug del código original)
        self.assertEqual(ctx.exception.code(), grpc.StatusCode.INTERNAL)
        self.assertIn("response_map", ctx.exception.details())


# ----------------------------------------------------------------------
# 3. PRUEBAS DE VALORES FRONTERA (coordenadas límite válidas)
# ----------------------------------------------------------------------
class TestBoundaryValues(unittest.TestCase):
    """
    En esta parte se prueban los valores frontera válidos, es decir,
    cuando la latitud o longitud están justo en los límites aceptados.
    """

    def test_boundary_latitude_longitude_values(self):
        """Verifica que las posiciones exactamente en los límites no generen excepción."""
        límites = [
            (90.0, 0.0),
            (-90.0, 0.0),
            (0.0, 180.0),
            (0.0, -180.0),
        ]
        for lat, lon in límites:
            try:
                pos = Position(lat, lon, 0.0)
                self.assertIsInstance(pos, Position)
            except ValueError:
                self.fail(f"Position({lat}, {lon}) lanzó ValueError indebidamente.")


# ----------------------------------------------------------------------
# Ejecución directa
# ----------------------------------------------------------------------
if __name__ == "__main__":
    unittest.main(verbosity=2)
