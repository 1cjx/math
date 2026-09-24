\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{my_paper}[2026/09/23 Compatibility class for supplied text template]
% 原附件没有提供 my_paper.cls。本文件只提供可移植的类入口，
% 不是对未提供的原类进行恢复；具体版式全部由 main.tex 明确设置。
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{ctexart}}
\ProcessOptions\relax
\LoadClass[UTF8,zihao=-4,fontset=fandol]{ctexart}
