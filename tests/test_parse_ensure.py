from pybel.parser.test_utils import TestTokenParserBase


class TestEnsure(TestTokenParserBase):
    def test_complete_origin(self):
        """"""
        statement = 'p(HGNC:AKT1)'
        result = self.parser.protein.parseString(statement)

        expected_result = ['Protein', ['HGNC', 'AKT1']]
        self.assertEqual(expected_result, result.asList())

        protein = 'Protein', 'HGNC', 'AKT1'
        rna = 'RNA', 'HGNC', 'AKT1'
        gene = 'Gene', 'HGNC', 'AKT1'

        self.assertHasNode(protein, type='Protein', namespace='HGNC', name='AKT1')
        self.assertHasNode(rna, type='RNA', namespace='HGNC', name='AKT1')
        self.assertHasNode(gene, type='Gene', namespace='HGNC', name='AKT1')

        self.assertEqual(2, self.parser.graph.number_of_edges())

        self.assertHasEdge(gene, rna, relation='transcribedTo')
        self.assertEqual(1, self.parser.graph.number_of_edges(gene, rna))

        self.assertHasEdge(rna, protein, relation='translatedTo')
        self.assertEqual(1, self.parser.graph.number_of_edges(rna, protein))

    def ensure_no_dup_nodes(self):
        """Ensure node isn't added twice, even if from different statements"""
        s1 = 'g(HGNC:AKT1)'
        s2 = 'deg(g(HGNC:AKT1))'
        s3 = 'deg(g(HGNC:AKT1)) -- g(HGNC:AKT1)'

        self.parser.statement.parseString(s1)
        self.parser.statement.parseString(s2)
        self.parser.statement.parseString(s3)

        gene = 'Gene', 'HGNC', 'AKT1'

        self.assertEqual(1, self.parser.graph)
        self.assertHasNode(gene, type='Gene', namespace='HGNC', value='AKT1')

    def ensure_no_dup_edges(self):
        """Ensure node and edges aren't added twice, even if from different statements and has origin completion"""
        s1 = 'g(HGNC:AKT1)'
        s2 = 'deg(p(HGNC:AKT1))'
        s3 = 'deg(p(HGNC:AKT1)) -- g(HGNC:AKT1)'

        self.parser.statement.parseString(s1)
        self.parser.statement.parseString(s2)
        self.parser.statement.parseString(s3)

        protein = 'Protein', 'HGNC', 'AKT1'
        rna = 'RNA', 'HGNC', 'AKT1'
        gene = 'Gene', 'HGNC', 'AKT1'

        self.assertEqual(3, self.parser.graph)
        self.assertHasNode(protein, type='Protein', namespace='HGNC', value='AKT1')
        self.assertHasNode(rna, type='RNA', namespace='HGNC', value='AKT1')
        self.assertHasNode(gene, type='Gene', namespace='HGNC', value='AKT1')

        self.assertEqual(2, self.parser.graph.number_of_edges())

        self.assertHasEdge(gene, rna, relation='transcribedTo')
        self.assertEqual(1, self.parser.graph.number_of_edges(gene, rna))

        self.assertHasEdge(rna, protein, relation='translatedTo')
        self.assertEqual(1, self.parser.graph.number_of_edges(rna, protein))
