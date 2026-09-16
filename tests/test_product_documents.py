import base64
import io
from unittest.mock import patch
from PyPDF2 import PdfFileWriter
from PIL import Image
from odoo.exceptions import AccessError, ValidationError, UserError, MissingError
from odoo.tests.common import TransactionCase, tagged
from ..models.product_documents import empty_panel, document_url, pdf_upload


@tagged('-at_install','post_install')
class TestProductDocuments(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env['product.template'].create({'name':'Document fixture','sale_ok':True})
        cls.service = cls.env['bpi.service']
        cls.panels = cls.env['bpi.product.document.panel']
        cls.website = cls.env['website'].search([],limit=1)
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({'name':'Documents reader','login':'bpi_document_reader','groups_id':[(6,0,cls.env.ref('base.group_user').ids)]})

    def pdf(self):
        writer=PdfFileWriter();writer.addBlankPage(width=100,height=100)
        out=io.BytesIO();writer.write(out)
        return base64.b64encode(out.getvalue()).decode()

    def values(self):
        data=empty_panel();data['title']='Catálogo <script>escaped</script>';data['intro']='Conoce todos los detalles.'
        data['buttons'][0].update(label='Ver catálogo',url='https://example.com/catalog.pdf')
        return data

    def save(self,data):
        return self.service.save_content(self.product,{'documents':data})

    def test_empty_block_hidden_and_opening_does_not_create_or_call_provider(self):
        with patch.object(type(self.service),'_openai_request',side_effect=AssertionError('No external call')):
            self.assertEqual(self.product.bpi_build_payload()['documents'],empty_panel())
            self.assertFalse(self.panels.search([('product_id','=',self.product.id)]))
            self.product.website_published=True
            self.assertFalse(self.product._bpi_public_document_panel(self.website))

    def test_url_save_projection_and_publication_gate(self):
        data=self.values();result=self.save(data)['documents']
        self.assertEqual(result['revision'],1)
        self.assertFalse(self.product._bpi_public_document_panel(self.website))
        self.product.website_published=True
        public=self.product._bpi_public_document_panel(self.website)
        self.assertEqual(len(public['buttons']),1)
        self.assertEqual(public['buttons'][0]['url'],'https://example.com/catalog.pdf')
        self.product.active=False
        self.assertFalse(self.product._bpi_public_document_panel(self.website))

    def test_noop_and_stale_revision(self):
        data=self.save(self.values())['documents'];self.save(data)
        self.assertEqual(self.product.bpi_build_payload()['documents']['revision'],1)
        data['title']='New';saved=self.save(data)['documents'];self.assertEqual(saved['revision'],2)
        with self.assertRaises(UserError):self.save(data)
        self.assertEqual(self.product.bpi_build_payload()['documents']['title'],'New')

    def test_pdf_private_attachment_and_metadata_only_payload(self):
        data=self.values();data['buttons'][1].update(label='Ficha técnica',kind='file',upload=self.pdf(),filename='ficha.pdf')
        result=self.save(data)['documents'];self.assertTrue(result['buttons'][1]['hasFile'])
        self.assertNotIn('upload',result['buttons'][1]);self.assertIn('/2?v=1',result['buttons'][1]['fileUrl'])
        panel=self.panels.search([('product_id','=',self.product.id)])
        attachments=self.env['ir.attachment'].search([('res_model','=',panel._name),('res_id','=',panel.id),('res_field','in',['file_1','file_2','file_3','cover'])])
        self.assertTrue(attachments);self.assertFalse(any(attachments.mapped('public')))
        with self.assertRaises(AccessError):panel.with_user(self.user).read(['file_2'])
        # A later unrelated content save keeps the uploaded document.
        self.save(result);self.assertEqual(self.product.bpi_build_payload()['documents']['revision'],1)

    def test_cover_validation_and_removal(self):
        out=io.BytesIO();Image.new('RGB',(12,12),'white').save(out,'PNG')
        data=self.values();data['cover']=base64.b64encode(out.getvalue()).decode()
        result=self.save(data)['documents'];self.assertIn('/cover?v=1',result['coverUrl'])
        self.assertNotIn('cover',result)
        result['cover']=False;self.assertFalse(self.save(result)['documents']['coverUrl'])
        data['cover']=base64.b64encode(b'<svg onload="x"/>').decode()
        data['revision']=2
        with self.assertRaises(ValidationError):self.save(data)

    def test_invalid_links_are_not_saved_or_fetched(self):
        for url in ('javascript:alert(1)','data:text/html,x','http://example.com/a','https://u:p@example.com/a','https://127.0.0.1/a','https://[::1]/a','https://service.local/a','https://example.com/\nx'):
            with self.subTest(url=url),self.assertRaises(ValidationError):document_url(url)
        self.assertEqual(document_url('https://example.com/a?b=c#x'),'https://example.com/a?b=c#x')

    def test_invalid_pdf_and_oversized_payload(self):
        for value in ('not-base64',base64.b64encode(b'<html>not PDF</html>'),base64.b64encode(b'%PDF-1.4 broken')):
            with self.assertRaises(ValidationError):pdf_upload(value)
        writer=PdfFileWriter();writer.addBlankPage(width=100,height=100);writer.addJS('app.alert("x")')
        out=io.BytesIO();writer.write(out)
        with self.assertRaises(ValidationError):pdf_upload(base64.b64encode(out.getvalue()))
        with self.assertRaises(ValidationError):pdf_upload('A'*(14*1024*1024))

    def test_partial_button_validation_and_atomic_failure(self):
        for changes in ({'label':'Catalog','url':''},{'label':'','url':'https://example.com/a'},{'label':'PDF','kind':'file','filename':'a.pdf'}):
            data=empty_panel();data['buttons'][0].update(changes)
            with self.assertRaises(ValidationError):self.save(data)
        before=self.product.bpi_ai_generated_description
        with self.assertRaises(ValidationError):
            self.service.save_content(self.product,{'description':'Do not save','documents':{'revision':0,'buttons':[]}})
        self.assertEqual(self.product.bpi_ai_generated_description,before)
        with self.assertRaises(ValueError):
            self.service.save_content(self.product,{'documents':self.values(),'tone':'not-a-valid-tone'})
        self.assertFalse(self.panels.search([('product_id','=',self.product.id)]))

    def test_context_company_and_nonmanager_writes(self):
        with self.assertRaises(AccessError):self.service.with_user(self.user).save_content(self.product,{'documents':self.values()})
        other=self.env['res.company'].create({'name':'Documents other company'})
        foreign=self.env['product.template'].create({'name':'Foreign documents','company_id':other.id})
        with self.assertRaises(MissingError):
            self.service.with_context(allowed_company_ids=[self.env.company.id]).save_content(foreign,{'documents':self.values()})
        self.product.website_published=True
        self.product.company_id=other
        self.assertFalse(self.product._bpi_public_document_panel(self.website))

    def test_remove_all_buttons_hides_public_block(self):
        saved=self.save(self.values())['documents'];saved['buttons']=empty_panel()['buttons']
        self.save(saved);self.product.website_published=True
        self.assertFalse(self.product._bpi_public_document_panel(self.website))
        self.assertEqual(self.product.bpi_build_payload()['documents']['title'],self.values()['title'])

    def test_other_website_cannot_project_documents(self):
        self.save(self.values());self.product.website_published=True
        other=self.env['website'].create({'name':'Documents second website','company_id':self.website.company_id.id})
        self.product.website_id=other
        self.assertFalse(self.product._bpi_public_document_panel(self.website))
        self.assertTrue(self.product._bpi_public_document_panel(other))

    def test_model_write_guards_and_attachment_cleanup(self):
        data=self.values();data['buttons'][0].update(kind='file',upload=self.pdf(),filename='catalog.pdf',url='')
        self.save(data);panel=self.panels.search([('product_id','=',self.product.id)])
        with self.assertRaises(AccessError):panel.with_user(self.user).write({'title':'No'})
        with self.assertRaises(ValidationError):panel.write({'revision':999})
        with self.assertRaises(ValidationError):panel.write({'product_id':self.product.id})
        pid=panel.id;panel.unlink()
        self.assertFalse(self.env['ir.attachment'].search([('res_model','=',panel._name),('res_id','=',pid),('res_field','in',['file_1','cover'])]))
