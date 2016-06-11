TOOL?=pdflatex

all:
	@echo "alvos disponiveis: clean, minuta, pp (pre-projeto), tcc, dez11"

clean: distclean
	-@rm -fv *.dvi *.pdf

distclean:
	-@rm -fv *.bbl *.log *.blg *.aux *.out *.nav *.snm *.toc
	-@rm -fv apresentacao-dez-2011/*.pdf apresentacao-dez-2011/*~ pre-projeto/*.pdf
	-@rm -fv apresentacao-fev-2011/*.pdf apresentacao-fev-2012/*~

dez11:
	$(TOOL) apresentacao-dez-2011
	$(TOOL) apresentacao-dez-2011

fev12:
	$(TOOL) apresentacao-fev-2012
	$(TOOL) apresentacao-fev-2012


minuta:
	$(TOOL) minuta
	bibtex  minuta
	$(TOOL) minuta
	$(TOOL) minuta

pp:
	$(TOOL) pre-projeto
	bibtex  pre-projeto
	$(TOOL) pre-projeto
	$(TOOL) pre-projeto
	$(TOOL) pre-projeto

artjun:
	$(TOOL) artigo-junho
	bibtex  artigo-junho
	$(TOOL) artigo-junho
	$(TOOL) artigo-junho
	$(TOOL) artigo-junho

app:
	$(TOOL) apresentacao-pre-projeto
	$(TOOL) apresentacao-pre-projeto

tcc:
	$(TOOL) tcc
	bibtex  tcc
	$(TOOL) tcc
	$(TOOL) tcc






