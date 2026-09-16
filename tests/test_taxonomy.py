from unittest.mock import patch
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError, UserError, ValidationError, MissingError
from ..models.taxonomy import normalize, digest


@tagged('-at_install', 'post_install')
class TestTaxonomy(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env['bpi.service']
        cls.Term = cls.env['bpi.taxonomy.term']
        cls.Model = cls.env['product.template']
        cls.product = cls.Model.create({'name':'Fórceps fixture', 'default_code':'TX/Á-01', 'sale_ok':True})
        cls.other = cls.Model.create({'name':'Instrumento fixture', 'default_code':'TX/02', 'sale_ok':True})
        cls.use = cls.Term.create({'name':'Retirada fixture', 'axis':'use', 'aliases_text':'exodoncia fixture', 'state':'approved'})
        cls.technical = cls.Term.create({'name':'Cirugía fixture', 'axis':'technical', 'state':'approved'})
        cls.niche = cls.Term.create({'name':'Clínica fixture', 'axis':'niche', 'state':'approved'})
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({'name':'Taxonomy reader','login':'taxonomy_reader','groups_id':[(6,0,cls.env.ref('base.group_user').ids)]})
        cls.website = cls.env['website'].search([],limit=1)

    def values(self, ids=None, product=None):
        product = product or self.product
        return {'classification':{'revision':product.bpi_classification_revision,'vocabularyRevision':self.Term._revision(),'termIds':ids or []}}

    def save(self, ids, product=None):
        p = product or self.product
        return self.service.save_category(p,self.values(ids,p))

    def test_approved_save_and_no_category_move(self):
        cats = self.product.public_categ_ids; internal = self.product.categ_id
        self.save([self.use.id,self.technical.id,self.niche.id])
        self.assertEqual(set(self.product.bpi_taxonomy_term_ids.ids),{self.use.id,self.technical.id,self.niche.id})
        self.assertEqual(self.product.public_categ_ids,cats);self.assertEqual(self.product.categ_id,internal)
        self.assertEqual(self.product.bpi_classification_revision,1)
        self.save(self.product.bpi_taxonomy_term_ids.ids)
        self.assertEqual(self.product.bpi_classification_revision,1)

    def test_draft_rejected_and_approval_does_not_assign(self):
        term=self.Term.create({'name':'Pendiente fixture','axis':'use'})
        with self.assertRaises(ValidationError):self.save([term.id])
        term.action_approve();self.assertFalse(self.product.bpi_taxonomy_term_ids)
        self.save([term.id]);self.assertEqual(self.product.bpi_taxonomy_term_ids,term)

    def test_revision_guards(self):
        old=self.values([self.use.id]);self.save([self.niche.id])
        with self.assertRaises(UserError):self.service.save_category(self.product,old)
        fresh=self.values([self.use.id]);self.use.write({'definition':'Updated'})
        with self.assertRaises(UserError):self.service.save_category(self.product,fresh)

    def test_used_term_protected_and_replacement(self):
        self.save([self.use.id])
        with self.assertRaises(UserError):self.use.unlink()
        with self.assertRaises(UserError):self.use.write({'active':False})
        replacement=self.Term.create({'name':'Sustitución fixture','axis':'use','state':'approved'})
        self.use.replacement_id=replacement;self.use.action_replace()
        self.assertEqual(self.product.bpi_taxonomy_term_ids,replacement);self.assertFalse(self.use.active)

    def test_alias_collision_and_invalid_sizes(self):
        with self.assertRaises(ValidationError):self.Term.create({'name':'Duplicado fixture','axis':'use','aliases_text':'EXODÓNCIA FIXTURE','state':'approved'})
        with self.assertRaises(ValidationError):self.Term.create({'name':'x'*101,'axis':'use'})
        self.assertEqual(normalize('  EXTRACCIÓN  dental '),'extraccion dental')

    def test_manual_permissions_and_direct_write_guards(self):
        with self.assertRaises(AccessError):self.Term.with_user(self.user).create({'name':'bad','axis':'use'})
        with self.assertRaises(AccessError):self.product.with_user(self.user).write({'bpi_taxonomy_term_ids':[(6,0,[self.use.id])]})
        with self.assertRaises(ValidationError):self.product.write({'bpi_classification_revision':9})
        with self.assertRaises(ValidationError):self.Term.write({'revision':9})

    def test_copy_has_no_approved_classification(self):
        self.save([self.use.id]);copy=self.product.copy()
        self.assertFalse(copy.bpi_taxonomy_term_ids);self.assertEqual(copy.bpi_classification_revision,0)

    def test_legacy_suggestion_not_assignment(self):
        self.product.write({'bpi_intelligent_niches':['clinica'], 'bpi_intelligent_type':'instrumental'})
        data=self.product._bpi_classification_payload()
        self.assertTrue(data['legacyTermIds']);self.assertFalse(data['termIds'])

    def test_synonym_and_composed_query(self):
        self.save([self.use.id,self.technical.id])
        domain=self.Model._bpi_query_domain('EXODÓNCIA fixture cirugía fixture')
        matches=self.Model.search(domain)
        self.assertIn(self.product,matches);self.assertNotIn(self.other,matches)
        self.assertNotIn(self.product,self.Model.search(self.Model._bpi_query_domain('exodoncia fixture nonexistent')))

    def test_or_within_axis_and_across_axes(self):
        self.save([self.use.id,self.niche.id]);self.save([self.technical.id],self.other)
        domain=self.Model._bpi_filter_domain([self.use.id,self.technical.id])
        self.assertNotIn(self.product,self.Model.search(domain));self.assertNotIn(self.other,self.Model.search(domain))
        alternative=self.Term.create({'name':'Alternativa fixture','axis':'use','state':'approved'})
        self.assertIn(self.product,self.Model.search(self.Model._bpi_filter_domain([self.use.id,alternative.id,self.niche.id])))

    def test_rank_before_pagination_and_sku_variant(self):
        exact=self.Model.create({'name':'ZZZ Fixture','default_code':'exodoncia fixture'})
        self.save([self.use.id]);domain=self.Model._bpi_query_domain('exodoncia fixture')
        page=self.Model._bpi_ranked_search(domain,'exodoncia fixture',limit=1)
        self.assertEqual(page,exact)
        self.assertEqual(self.Model._bpi_ranked_search(domain,'exodoncia fixture',offset=1,limit=1),self.product)
        self.assertIn(self.product,self.Model.search(self.Model._bpi_query_domain('tx/a-01')))

    def test_unclassified_identity_and_empty_catalog(self):
        self.assertIn(self.other,self.Model.search(self.Model._bpi_query_domain('instrumento fixture')))
        self.assertFalse(self.Model.search(self.Model._bpi_query_domain('noexistentxyz')))
        self.assertFalse(self.Model._bpi_facets([('id','=',0)])[0]['count'])

    def test_facets_counts_and_draft_exclusion(self):
        self.save([self.use.id,self.niche.id]);self.save([self.use.id],self.other)
        facets=self.Model._bpi_facets([('id','in',[self.product.id,self.other.id])])
        counts={t['id']:t['count'] for t in facets}
        self.assertEqual(counts[self.use.id],2);self.assertEqual(counts[self.niche.id],1)
        draft=self.Term.create({'name':'Unseen fixture','axis':'use'})
        self.assertNotIn(draft.id,{t['id'] for t in self.Term._catalog()})
        self.assertNotIn(draft.id,{t['id'] for t in self.Term.with_context(active_test=False)._catalog()})

    def test_universal_wholesaler_does_not_assign_niches(self):
        universal=next(t for t in self.Term._catalog() if t['universal'])
        self.assertIn(self.other, self.Model.search(self.Model._bpi_filter_domain([universal['id'],self.niche.id])))
        with self.assertRaises(ValidationError):self.save([universal['id']])

    def test_invalid_filters(self):
        for value in ['1,abc',{},[True],[999999999],'-1']:
            with self.subTest(value=value),self.assertRaises(ValidationError):self.Model._bpi_filter_ids(value)

    def test_website_search_context_and_no_external_calls(self):
        self.save([self.use.id]);self.product.website_published=True
        self.website.bpi_taxonomy_search_enabled=True
        options={'displayImage':False,'displayDescription':False,'displayExtraLink':False,'displayDetail':False}
        detail=self.Model._search_get_detail(self.website,'id',options)
        with patch.object(type(self.service),'_openai_request',side_effect=AssertionError('Search never calls providers')):
            result,count=self.Model._search_fetch(detail,'exodoncia fixture',8,'id')
        self.assertIn(self.product,result);self.assertEqual(count,1)
        self.product.website_published=False
        self.assertFalse(self.Model._search_fetch(detail,'exodoncia fixture',8,'id')[0])

    def test_job_dedup_no_paid_call_on_creation(self):
        jobs=self.env['bpi.ai.job'].with_user(self.env.ref('base.user_admin')).with_context(bpi_no_job_commit=True)
        with patch.object(type(self.service),'_openai_request',side_effect=AssertionError('Creation never calls provider')):
            a=jobs._create_classification_job(self.product);b=jobs._create_classification_job(self.product)
        self.assertEqual(a,b);self.assertFalse(self.product.bpi_taxonomy_term_ids)

    def test_job_proposal_does_not_write_product(self):
        job=self.env['bpi.ai.job'].with_user(self.env.ref('base.user_admin')).with_context(bpi_no_job_commit=True)._create_classification_job(self.product)
        with patch.object(type(self.service),'_openai_json',return_value={'termIds':[self.use.id],'reasons':'Confirmed saved data','warnings':[],'newTerms':[{'axis':'use','name':'Nueva propuesta fixture','definition':'Pending','aliases':[]}]}):
            job._process_job()
        self.assertEqual(job.state,'done', job.error_message);self.assertFalse(self.product.bpi_taxonomy_term_ids)
        self.assertEqual(job.result_payload['classificationProposal']['termIds'],[self.use.id])
        self.assertEqual(self.Term.search([('name','=','Nueva propuesta fixture')]).state,'draft')

    def test_stale_source_prevents_paid_call(self):
        job=self.env['bpi.ai.job'].with_user(self.env.ref('base.user_admin')).with_context(bpi_no_job_commit=True)._create_classification_job(self.product)
        self.product.name='Changed source'
        with patch.object(type(self.service),'_openai_json',side_effect=AssertionError('No paid request')):job._process_job()
        self.assertEqual(job.state,'failed')

    def test_atomic_full_save_rollback(self):
        data=self.values([self.use.id])
        with self.assertRaises(ValueError):
            self.service.save_all(self.product,category_values=data,content_values={'tone':'invalid tone'})
        self.assertFalse(self.product.bpi_taxonomy_term_ids)

    def test_search_website_and_company_isolation(self):
        company=self.env['res.company'].create({'name':'Taxonomy isolated company'})
        site=self.env['website'].create({'name':'Taxonomy isolated website','company_id':company.id})
        self.website.bpi_taxonomy_search_enabled=True
        self.product.write({'name':'Isolation needle','website_id':self.website.id,'is_published':True})
        self.other.write({'name':'Isolation needle','website_id':site.id,'company_id':company.id,'is_published':True})
        self.save([self.use.id])
        detail=self.Model.with_context(website_id=self.website.id)._search_get_detail(self.website.with_context(website_id=self.website.id),'name',{'bpiTermIds':[self.use.id],'displayImage':False,'displayDescription':False,'displayExtraLink':False,'displayDetail':False})
        self.other.with_context(allowed_company_ids=[self.website.company_id.id,company.id]).write({'bpi_taxonomy_term_ids':[(6,0,[self.use.id])]})
        results,count=self.Model._search_fetch(detail,'exodoncia fixture',20,'name')
        self.assertIn(self.product,results);self.assertNotIn(self.other,results)
        limited=self.service.with_user(self.env.ref('base.user_admin')).with_context(allowed_company_ids=[self.website.company_id.id])
        with self.assertRaises(MissingError):limited._meli_product(self.other.id)

    def test_proposed_alias_existing_term_requires_manual_approval(self):
        prior=self.use.aliases_text;rev=self.Term._revision()
        with patch.object(type(self.service),'_openai_json',return_value={'termIds':[self.use.id],'reasons':'Review alias','warnings':[], 'newTerms':[{'axis':'use','name':self.use.name,'aliases':['nuevo alias pendiente']}] }):
            proposal=self.service._classification_proposal(self.product,self.product._bpi_classification_source(),self.Term._catalog())
        self.assertEqual(self.use.aliases_text,prior);self.assertEqual(self.Term._revision(),rev)
        self.assertIn('nuevo alias pendiente',proposal['newTerms'][0]['aliases_text'])
        self.assertFalse(self.product.bpi_taxonomy_term_ids)


    def test_job_preserves_request_language(self):
        self.product.with_context(lang='es_ES').name='Pinza guardada español'
        jobs=self.env['bpi.ai.job'].with_user(self.env.ref('base.user_admin')).with_context(lang='es_ES',bpi_no_job_commit=True)
        job=jobs._create_classification_job(self.product.with_env(jobs.env))
        with patch.object(type(self.service),'_openai_json',return_value={'termIds':[], 'reasons':'Sin evidencia suficiente','warnings':[],'newTerms':[]}):
            job.with_context(lang='en_US')._process_job()
        self.assertEqual(job.state,'done',job.error_message)

    def test_manual_exclusions_persist_and_reselect_clears(self):
        values=self.values([]);values['classification']['excludedTermIds']=[self.use.id]
        self.service.save_category(self.product,values)
        self.assertEqual(self.product._bpi_classification_payload()['excludedTermIds'],[self.use.id])
        # Old clients omit the new key: selecting the term explicitly removes its exclusion.
        self.save([self.use.id])
        self.assertFalse(self.product.bpi_classification_excluded_ids)
        self.assertEqual(self.product.bpi_taxonomy_term_ids,self.use)

    def test_exclusions_permissions_validation_and_copy(self):
        with self.assertRaises(AccessError):self.product.with_user(self.user).write({'bpi_classification_excluded_ids':[self.use.id]})
        for value in [[True],[9999999],'invalid']:
            data=self.values();data['classification']['excludedTermIds']=value
            with self.assertRaises(ValidationError):self.service.save_category(self.product,data)
        self.product.write({'bpi_classification_excluded_ids':[self.use.id]})
        self.assertFalse(self.product.copy().bpi_classification_excluded_ids)
        self.assertFalse(self.Model.search([('id','=',self.product.id)]+self.Model._bpi_query_domain('exodoncia fixture')))

    def test_exclusions_save_all_failure_is_atomic(self):
        data=self.values();data['classification']['excludedTermIds']=[self.use.id]
        with self.assertRaises(ValueError):self.service.save_all(self.product,category_values=data,content_values={'tone':'invalid tone'})
        self.assertFalse(self.product.bpi_classification_excluded_ids)
