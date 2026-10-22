import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('cartao', Path(__file__).parents[1] / 'gerar-cartao.py')
cartao = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cartao)


class CartaoTest(unittest.TestCase):
    def test_fim_de_frase_e_limite(self):
        texto = 'Uma vida a serviço de Maria. ' + 'Uma frase muito longa ' * 20
        self.assertEqual(cartao.trecho(texto), 'Uma vida a serviço de Maria.')

    def test_primeira_frase_longa_sem_cortar_palavra(self):
        texto = 'Fraternidade e serviço ' * 20
        resultado = cartao.trecho(texto)
        self.assertLessEqual(len(resultado), 140)
        self.assertTrue(texto.startswith(resultado))
        self.assertEqual(texto[len(resultado)], ' ')
        self.assertNotIn('…', resultado)

    def test_inicial_nao_e_fim_de_frase(self):
        texto = 'Frei Paulino M. Baldassarri ' + 'serviu a comunidade ' * 20
        self.assertIn('Baldassarri', cartao.trecho(texto))

    def test_legenda_sem_inferir_grau(self):
        texto = cartao.legenda('Nome de teste', '', '8 de abril', 'https://example.invalid/post-de-teste')
        self.assertIn('https://example.invalid/post-de-teste', texto)
        self.assertIn('https://' + cartao.LINK + '/', texto)
        self.assertNotIn('Memória', texto)
        self.assertNotIn('Ofício', texto)

    def test_legenda_rejeita_link_invalido(self):
        with self.assertRaises(ValueError):
            cartao.legenda('Nome', '', '8 de abril', 'link ausente')


if __name__ == '__main__':
    unittest.main()
